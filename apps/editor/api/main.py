from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai_service import AIService
from .config import get_settings
from .content_store import ContentStore
from .git_service import GitService
from .markdown_preview import render_markdown, render_translation_provenance
from .publish_service import PublishService
from .social.router import build_social_router
from .models import (
    ConfigResponse,
    CreatePostRequest,
    PostDocument,
    PostSummary,
    PreviewRequest,
    PreviewResponse,
    PublishResponse,
    SimpleValueResponse,
    SuggestionsResponse,
    TranslateRequest,
    UpdatePostRequest,
)

settings = get_settings()
store = ContentStore(settings)
git_service = GitService(settings)
ai_service = AIService(settings)
publish_service = PublishService(settings, store, git_service)

app = FastAPI(title="Darjeeling Blog Editor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{settings.host}:{settings.port}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=settings.static_root), name="static")
app.include_router(build_social_router(settings, ai_service, store))


def _handle_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/", response_class=FileResponse)
async def editor_index() -> FileResponse:
    return FileResponse(settings.static_root / "index.html")


@app.get("/api/config", response_model=ConfigResponse)
async def api_config() -> ConfigResponse:
    return ConfigResponse(
        default_lang=settings.default_lang,
        draft_root=str(settings.draft_root.relative_to(settings.repo_root)),
        article_root=str(settings.article_root.relative_to(settings.repo_root)),
        ai_enabled=settings.ai_enabled,
        openai_model=settings.openai_model,
    )


@app.get("/api/posts", response_model=list[PostSummary])
async def list_posts() -> list[PostSummary]:
    return store.list_documents()


@app.post("/api/posts", response_model=PostDocument)
async def create_post(request: CreatePostRequest) -> PostDocument:
    try:
        return store.create_draft(request)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.get("/api/posts/{post_path:path}", response_model=PostDocument)
async def get_post(post_path: str) -> PostDocument:
    try:
        return store.read_document(post_path)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.put("/api/posts/{post_path:path}", response_model=PostDocument)
async def update_post(post_path: str, request: UpdatePostRequest) -> PostDocument:
    try:
        return store.write_document(request, path=post_path)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/posts/{post_path:path}/preview", response_model=PreviewResponse)
async def preview_post(post_path: str, request: PreviewRequest) -> PreviewResponse:
    try:
        body_html = render_markdown(request.body_markdown)
        provenance_html = render_translation_provenance(
            request.translation_model,
            request.translation_at,
            request.translation_source_lang,
        )
        return PreviewResponse(body_html=body_html, provenance_html=provenance_html)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/posts/{post_path:path}/publish", response_model=PublishResponse)
async def publish_post(post_path: str) -> PublishResponse:
    try:
        return publish_service.publish(post_path)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/posts/{post_path:path}/unpublish", response_model=PostDocument)
async def unpublish_post(post_path: str) -> PostDocument:
    try:
        return store.unpublish(post_path)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/ai/title", response_model=SuggestionsResponse)
async def ai_title(document: PostDocument) -> SuggestionsResponse:
    try:
        return SuggestionsResponse(values=await ai_service.suggest_titles(document))
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/ai/tags", response_model=SuggestionsResponse)
async def ai_tags(document: PostDocument) -> SuggestionsResponse:
    try:
        return SuggestionsResponse(values=await ai_service.suggest_tags(document))
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/ai/slug", response_model=SimpleValueResponse)
async def ai_slug(document: PostDocument) -> SimpleValueResponse:
    try:
        return SimpleValueResponse(value=await ai_service.suggest_slug(document))
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/ai/summary", response_model=SimpleValueResponse)
async def ai_summary(document: PostDocument) -> SimpleValueResponse:
    try:
        return SimpleValueResponse(value=await ai_service.suggest_summary(document))
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


@app.post("/api/ai/translate", response_model=PostDocument)
async def ai_translate(request: TranslateRequest) -> PostDocument:
    try:
        source = store.read_document(request.source_path)
        translation = await ai_service.translate(source, request.target_lang)
        translation_model, translation_at = ai_service.translation_metadata()
        return store.create_or_update_translation(
            source=source,
            target_lang=request.target_lang,
            title=translation.title,
            summary=translation.summary,
            body_markdown=translation.body_markdown,
            translation_model=translation_model,
            translation_at=translation_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc) from exc


def main() -> None:
    import uvicorn

    uvicorn.run(
        "apps.editor.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
