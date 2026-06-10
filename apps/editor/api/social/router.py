from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from ..ai_service import AIService
from ..config import EditorSettings
from ..content_store import ContentStore
from .config import SocialConfig
from .models import (
    AccountStatus,
    AddPersonRequest,
    AltTextRequest,
    CreateDraftRequest,
    InstagramPackage,
    MentionEntry,
    NetworkRender,
    PublishRequest,
    PublishResponse,
    PublishResult,
    SnsDraft,
    SnsImage,
    UpdateDraftRequest,
    UpdateRenderRequest,
)
from .service import SocialService
from .store import SocialStore
from .sync import DraftSync


def build_social_router(
    settings: EditorSettings,
    ai_service: AIService,
    content_store: ContentStore,
) -> APIRouter:
    config = SocialConfig(settings)
    store = SocialStore(config.db_path)
    service = SocialService(config, store, ai_service, content_store)
    syncer = DraftSync(store, config.drafts_dir, config.drafts_key)
    if syncer.enabled:
        # pick up bundles pulled from other devices before serving anything
        syncer.import_all()

    router = APIRouter(prefix="/api/social", tags=["social"])

    def _error(exc: Exception) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))

    def _export(draft_id: str) -> None:
        try:
            syncer.export_draft(draft_id)
        except Exception:  # noqa: BLE001 - sync must never break editing
            pass

    @router.get("/accounts", response_model=list[AccountStatus])
    async def list_accounts() -> list[AccountStatus]:
        return service.account_statuses()

    @router.get("/drafts", response_model=list[SnsDraft])
    async def list_drafts() -> list[SnsDraft]:
        return store.list_drafts()

    @router.post("/drafts", response_model=SnsDraft)
    async def create_draft(request: CreateDraftRequest) -> SnsDraft:
        try:
            draft = store.create_draft(
                source=request.source,
                base_lang=request.base_lang,
                base_text=request.base_text,
                article_path=request.article_path,
                link=request.link,
            )
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc
        _export(draft.id)
        return draft

    @router.get("/drafts/{draft_id}", response_model=SnsDraft)
    async def get_draft(draft_id: str) -> SnsDraft:
        try:
            return store.get_draft(draft_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/drafts/{draft_id}", response_model=SnsDraft)
    async def update_draft(draft_id: str, request: UpdateDraftRequest) -> SnsDraft:
        try:
            draft = store.update_draft(
                draft_id,
                base_lang=request.base_lang,
                base_text=request.base_text,
                link=request.link,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _export(draft.id)
        return draft

    @router.delete("/drafts/{draft_id}")
    async def delete_draft(draft_id: str) -> dict[str, bool]:
        store.delete_draft(draft_id)
        syncer.remove_draft(draft_id)
        return {"ok": True}

    @router.post("/sync")
    async def sync_drafts() -> dict[str, int]:
        try:
            return syncer.sync()
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.post("/drafts/{draft_id}/render", response_model=list[NetworkRender])
    async def render_draft(
        draft_id: str, overwrite_manual: bool = False
    ) -> list[NetworkRender]:
        try:
            renders = await service.render(draft_id, overwrite_manual=overwrite_manual)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc
        _export(draft_id)
        return renders

    @router.get("/drafts/{draft_id}/renders", response_model=list[NetworkRender])
    async def get_renders(draft_id: str) -> list[NetworkRender]:
        return service.get_renders(draft_id)

    @router.put("/drafts/{draft_id}/renders/{account_id}", response_model=NetworkRender)
    async def update_render(
        draft_id: str, account_id: str, request: UpdateRenderRequest
    ) -> NetworkRender:
        try:
            render = service.update_render(draft_id, account_id, request.text)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _export(draft_id)
        return render

    @router.post("/drafts/{draft_id}/publish", response_model=PublishResponse)
    async def publish_draft(draft_id: str, request: PublishRequest) -> PublishResponse:
        try:
            status, results = await service.publish(
                draft_id, request.account_ids, force=request.force
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _export(draft_id)
        return PublishResponse(draft_status=status, results=results)

    @router.get("/drafts/{draft_id}/history", response_model=list[PublishResult])
    async def draft_history(draft_id: str) -> list[PublishResult]:
        return store.post_history(draft_id)

    @router.post("/drafts/{draft_id}/images", response_model=SnsImage)
    async def upload_image(draft_id: str, file: UploadFile) -> SnsImage:
        try:
            data = await file.read()
            image = service.add_image(draft_id, file.filename or "upload", data)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc
        _export(draft_id)
        return image

    @router.delete("/drafts/{draft_id}/images/{image_id}", response_model=SnsDraft)
    async def remove_image(draft_id: str, image_id: str) -> SnsDraft:
        try:
            draft = service.remove_image(draft_id, image_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _export(draft_id)
        return draft

    @router.get("/images/{image_id}")
    async def get_image(image_id: str) -> FileResponse:
        path = service.image_path(image_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"unknown image: {image_id}")
        return FileResponse(path, media_type="image/jpeg")

    @router.get("/images/{image_id}/instagram")
    async def get_instagram_image(image_id: str, aspect: str = "portrait") -> FileResponse:
        try:
            path = service.instagram_variant_path(image_id, aspect)
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc
        return FileResponse(
            path,
            media_type="image/jpeg",
            filename=f"instagram-{image_id}-{aspect}.jpg",
        )

    @router.get("/images/{image_id}/meta", response_model=SnsImage)
    async def get_image_meta(image_id: str) -> SnsImage:
        try:
            return store.get_image(image_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/images/{image_id}/alt-text", response_model=SnsImage)
    async def generate_alt_text(image_id: str, lang: str = "ko") -> SnsImage:
        try:
            return await service.generate_alt_text(image_id, lang)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.put("/images/{image_id}/alt-text", response_model=SnsImage)
    async def set_alt_text(image_id: str, request: AltTextRequest) -> SnsImage:
        try:
            return service.set_alt_text(image_id, request.lang, request.text)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/drafts/{draft_id}/instagram-package", response_model=InstagramPackage)
    async def instagram_package(draft_id: str, aspect: str = "portrait") -> InstagramPackage:
        try:
            return service.instagram_package(draft_id, aspect)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.get("/people/search", response_model=list[MentionEntry])
    async def search_people(network: str, q: str) -> list[MentionEntry]:
        try:
            return await service.search_people(network, q)
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.post("/people", response_model=MentionEntry)
    async def add_person(request: AddPersonRequest) -> MentionEntry:
        entry = MentionEntry(
            network=request.network,
            handle=request.handle,
            identifier=request.identifier,
            display_name=request.display_name,
        )
        store.upsert_mention(entry)
        return store.get_mention(request.network, request.handle) or entry

    @router.post("/people/used")
    async def mention_used(request: AddPersonRequest) -> dict[str, bool]:
        service.mark_mention_used(request.network, request.handle)
        return {"ok": True}

    @router.get("/oauth/linkedin/start")
    async def linkedin_oauth_start(account_id: str) -> dict[str, str]:
        try:
            return {"url": service.linkedin_client(account_id).authorize_url()}
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.get("/oauth/linkedin/callback", response_class=HTMLResponse)
    async def linkedin_oauth_callback(
        code: str = "", state: str = "", error: str = "", error_description: str = ""
    ) -> HTMLResponse:
        if error:
            return HTMLResponse(
                f"<h1>LinkedIn authorization failed</h1><p>{error}: {error_description}</p>",
                status_code=400,
            )
        account_id = store.consume_oauth_state(state)
        if account_id is None:
            return HTMLResponse("<h1>Invalid OAuth state</h1>", status_code=400)
        try:
            client_api = service.linkedin_client(account_id)
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                await client_api.exchange_code(http_client, code)
        except Exception as exc:  # noqa: BLE001
            return HTMLResponse(
                f"<h1>Token exchange failed</h1><p>{exc}</p>", status_code=400
            )
        return HTMLResponse(
            "<h1>LinkedIn authorized</h1><p>You can close this tab and return to the editor.</p>"
        )

    @router.get("/oauth/threads/start")
    async def threads_oauth_start(account_id: str) -> dict[str, str]:
        try:
            client_api = service.threads_client(account_id)
            return {"url": client_api.authorize_url(), "redirect_uri": client_api.redirect_uri}
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc

    @router.post("/oauth/threads/exchange")
    async def threads_oauth_exchange(payload: dict[str, str]) -> dict[str, str]:
        account_id = payload.get("account_id", "")
        redirect_url = payload.get("redirect_url", "")
        try:
            client_api = service.threads_client(account_id)
            code, state = client_api.parse_redirect(redirect_url)
            if store.consume_oauth_state(state) != account_id:
                raise ValueError("OAuth state mismatch; start authorization again")
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                await client_api.exchange_code(http_client, code)
        except Exception as exc:  # noqa: BLE001
            raise _error(exc) from exc
        return {"status": "authorized"}

    return router
