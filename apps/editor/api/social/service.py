from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import httpx

from ..ai_service import AIService
from ..content_store import ContentStore
from .clients import SocialApiError
from .clients.bluesky import BlueskyClient
from .clients.linkedin import LinkedInClient
from .clients.mastodon import MastodonClient
from .clients.threads import ThreadsClient
from .config import SocialConfig
from .images import instagram_variant, process_upload
from .models import (
    AccountStatus,
    AuthStatus,
    InstagramPackage,
    MentionEntry,
    NetworkRender,
    PublishResult,
    SnsDraft,
    SnsImage,
    SocialAccount,
)
from .store import SocialStore
from .text import adapt, compose, count_for

HTTP_TIMEOUT = 30.0
SITE_URL = "https://iz4u.net"


class SocialService:
    def __init__(
        self,
        config: SocialConfig,
        store: SocialStore,
        ai_service: AIService,
        content_store: ContentStore | None = None,
    ):
        self.config = config
        self.store = store
        self.ai_service = ai_service
        self.content_store = content_store

    # --- render pipeline ---

    async def render(self, draft_id: str, *, overwrite_manual: bool = False) -> list[NetworkRender]:
        draft = self.store.get_draft(draft_id)
        accounts = [a for a in self.config.accounts() if a.enabled]
        translations, failed_langs = await self._translations_for(draft, accounts)
        renders: list[NetworkRender] = []
        for account in accounts:
            existing = self.store.get_render(draft.id, account.id)
            if existing and existing.manually_edited and not overwrite_manual:
                renders.append(self._with_counts(existing, account))
                continue
            body = translations[account.lang]
            link = draft.link
            translated = account.lang != draft.base_lang and account.lang not in failed_langs
            sibling = self._article_sibling(draft, account.lang)
            if sibling is not None:
                # a human-written translation of the article exists: prefer its
                # real title/summary and language-specific URL over machine output
                body = "\n\n".join(filter(None, [sibling.title, sibling.summary]))
                link = f"{SITE_URL}/{sibling.slug}-{sibling.lang}.html"
                translated = account.lang != draft.base_lang
            text, _, _ = adapt(account.network, body, link)
            render = NetworkRender(
                draft_id=draft.id,
                account_id=account.id,
                lang=account.lang,
                text=text,
                translated=translated,
            )
            self.store.upsert_render(render)
            renders.append(self._with_counts(render, account))
        return renders

    def _article_sibling(self, draft: SnsDraft, lang: str):
        if (
            self.content_store is None
            or draft.source != "article"
            or not draft.article_path
            or lang == draft.base_lang
        ):
            return None
        try:
            source = self.content_store.read_document(draft.article_path)
        except Exception:  # noqa: BLE001
            return None
        if not source.translation_key:
            return None
        return self.content_store.find_translation_target(source.translation_key, lang)

    async def _translations_for(
        self, draft: SnsDraft, accounts: list[SocialAccount]
    ) -> tuple[dict[str, str], set[str]]:
        translations = {draft.base_lang: draft.base_text}
        failed: set[str] = set()
        source_sha = hashlib.sha256(draft.base_text.encode()).hexdigest()
        for lang in sorted({a.lang for a in accounts} - {draft.base_lang}):
            cached = self.store.get_translation(draft.id, lang, source_sha)
            if cached is None:
                try:
                    cached = await self.ai_service.translate_short(
                        draft.base_text, draft.base_lang, lang
                    )
                except Exception:  # noqa: BLE001
                    # AI unavailable: fall back to the original text; the render
                    # stays translated=False so the UI flags it for manual editing
                    translations[lang] = draft.base_text
                    failed.add(lang)
                    continue
                self.store.save_translation(draft.id, lang, source_sha, cached)
            translations[lang] = cached
        return translations, failed

    def get_renders(self, draft_id: str) -> list[NetworkRender]:
        accounts = {a.id: a for a in self.config.accounts()}
        return [
            self._with_counts(render, accounts[render.account_id])
            for render in self.store.get_renders(draft_id)
            if render.account_id in accounts
        ]

    def update_render(self, draft_id: str, account_id: str, text: str) -> NetworkRender:
        account = self.config.account(account_id)
        existing = self.store.get_render(draft_id, account_id)
        lang = existing.lang if existing else account.lang
        render = NetworkRender(
            draft_id=draft_id,
            account_id=account_id,
            lang=lang,
            text=text,
            translated=existing.translated if existing else False,
            manually_edited=True,
        )
        self.store.upsert_render(render)
        return self._with_counts(render, account)

    def _with_counts(self, render: NetworkRender, account: SocialAccount) -> NetworkRender:
        count = count_for(account.network, render.text)
        return render.model_copy(
            update={
                "count": count,
                "limit": account.char_limit,
                "over_limit": count > account.char_limit,
            }
        )

    # --- accounts ---

    def account_statuses(self) -> list[AccountStatus]:
        return [self._status_for(account) for account in self.config.accounts()]

    def _status_for(self, account: SocialAccount) -> AccountStatus:
        return AccountStatus(
            id=account.id,
            network=account.network,
            lang=account.lang,
            handle=account.handle,
            enabled=account.enabled,
            mode=account.mode,
            char_limit=account.char_limit,
            auth_status=self._auth_status(account),
        )

    def _auth_status(self, account: SocialAccount) -> AuthStatus:
        if account.network == "instagram":
            return "ok"
        if not self.config.has_secrets(account):
            return "missing_secret"
        if account.network in ("bluesky", "mastodon"):
            return "ok"
        # threads / linkedin acquire user tokens at runtime via OAuth
        token = self.store.get_token(account.id)
        if token is None:
            return "needs_auth"
        expires_at = token.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            return "expired"
        return "ok"

    # --- publish ---

    async def publish(
        self, draft_id: str, account_ids: list[str], *, force: bool = False
    ) -> tuple[str, list[PublishResult]]:
        draft = self.store.get_draft(draft_id)
        accounts = {account.id: account for account in self.config.accounts()}
        results: list[PublishResult] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # sequential on purpose: posts appear in account order and a failure
            # in one network never interleaves with the others
            for account_id in account_ids:
                results.append(
                    await self._publish_one(
                        client, draft, accounts.get(account_id), account_id, force=force
                    )
                )
        status = self._draft_status(draft)
        self.store.update_draft(draft.id, status=status)
        return status, results

    def _draft_status(self, draft: SnsDraft) -> str:
        """Derive draft status from the full post history, so publishing accounts
        one at a time converges to the same state as a single batched call."""
        posted = {entry.account_id for entry in self.store.post_history(draft.id)}
        api_ids = {
            account.id
            for account in self.config.accounts()
            if account.enabled and account.mode == "api"
        }
        if api_ids and api_ids <= posted:
            return "published"
        if posted:
            return "partial"
        return draft.status

    async def _publish_one(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        account: SocialAccount | None,
        account_id: str,
        *,
        force: bool = False,
    ) -> PublishResult:
        if account is None:
            return self._failure(account_id, f"unknown account: {account_id}")
        try:
            render = self._render_for_publish(draft, account)
            content_sha = hashlib.sha256(
                f"{account.id}:{render.text}".encode()
            ).hexdigest()
            if not force and self.store.was_posted(draft.id, account.id, content_sha):
                return self._failure(
                    account.id, "already posted identical content (use force to re-send)"
                )
            images = self._load_images(draft)
            result = await self._dispatch(client, draft, account, render, images, content_sha)
        except (SocialApiError, ValueError, KeyError) as exc:
            return self._failure(account_id, str(exc))
        if result.ok:
            self.store.record_post(draft.id, account.id, content_sha, result)
        return result

    def _render_for_publish(self, draft: SnsDraft, account: SocialAccount) -> NetworkRender:
        render = self.store.get_render(draft.id, account.id)
        if render is None:
            # no explicit render yet: fall back to base text + link as-is
            text = compose(draft.base_text, draft.link)
            render = NetworkRender(
                draft_id=draft.id,
                account_id=account.id,
                lang=draft.base_lang,
                text=text,
            )
        count = count_for(account.network, render.text)
        if count > account.char_limit:
            raise ValueError(
                f"text is {count} characters, over the {account.network} limit"
                f" of {account.char_limit}"
            )
        return render

    def _load_images(self, draft: SnsDraft) -> list[tuple[SnsImage, bytes]]:
        images: list[tuple[SnsImage, bytes]] = []
        for image_id in draft.image_ids:
            image = self.store.get_image(image_id)
            path = self.config.images_dir / f"{image.id}.jpg"
            images.append((image, path.read_bytes()))
        return images

    async def _dispatch(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        account: SocialAccount,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
        content_sha: str,
    ) -> PublishResult:
        if account.network == "mastodon":
            return await self._mastodon_client(account).publish(
                client, draft, render, images, idempotency_key=content_sha
            )
        if account.network == "bluesky":
            return await self._bluesky_client(account).publish(client, draft, render, images)
        if account.network == "linkedin":
            return await self.linkedin_client(account.id).publish(
                client, draft, render, images
            )
        if account.network == "threads":
            return await self.threads_client(account.id).publish(
                client, draft, render, images
            )
        raise ValueError(f"publishing to {account.network} is not supported")

    def _mastodon_client(self, account: SocialAccount) -> MastodonClient:
        token = self.config.secret(account.id, "ACCESS_TOKEN")
        if not token:
            raise ValueError(f"missing access token for {account.id}")
        return MastodonClient(account, token)

    def _bluesky_client(self, account: SocialAccount) -> BlueskyClient:
        password = self.config.secret(account.id, "APP_PASSWORD")
        if not password:
            raise ValueError(f"missing app password for {account.id}")
        return BlueskyClient(account, password, self.store)

    def _failure(self, account_id: str, message: str) -> PublishResult:
        return PublishResult(account_id=account_id, ok=False, error=message)

    def linkedin_client(self, account_id: str) -> LinkedInClient:
        account = self.config.account(account_id)
        client_id = self.config.secret(account_id, "CLIENT_ID")
        client_secret = self.config.secret(account_id, "CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError(f"missing client id/secret for {account_id}")
        # override when authorizing from another device (e.g. a tailnet URL);
        # the registered default only resolves on the machine running the editor
        redirect_uri = self.config.secret(account_id, "REDIRECT_URI") or (
            f"http://{self.config.settings.host}:{self.config.settings.port}"
            "/api/social/oauth/linkedin/callback"
        )
        return LinkedInClient(account, client_id, client_secret, self.store, redirect_uri)

    def threads_client(self, account_id: str) -> ThreadsClient:
        account = self.config.account(account_id)
        client_id = self.config.secret(account_id, "CLIENT_ID")
        client_secret = self.config.secret(account_id, "CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError(f"missing client id/secret for {account_id}")
        redirect_uri = self.config.secret(account_id, "REDIRECT_URI")
        if redirect_uri:
            return ThreadsClient(account, client_id, client_secret, self.store, redirect_uri)
        return ThreadsClient(account, client_id, client_secret, self.store)

    # --- people search ---

    async def search_people(self, network: str, query: str) -> list[MentionEntry]:
        cached = self.store.search_mentions(network, query)
        api_results: list[MentionEntry] = []
        account = self._searchable_account(network)
        if account is not None:
            try:
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    if network == "bluesky":
                        api_results = await self._bluesky_client(account).search_people(
                            client, query
                        )
                    elif network == "mastodon":
                        api_results = await self._mastodon_client(account).search_people(
                            client, query
                        )
            except (SocialApiError, ValueError):
                api_results = []  # degrade to cache-only on API failure
            for entry in api_results:
                self.store.upsert_mention(entry)
        seen = {entry.handle for entry in cached}
        return cached + [entry for entry in api_results if entry.handle not in seen]

    def _searchable_account(self, network: str) -> SocialAccount | None:
        if network not in ("bluesky", "mastodon"):
            return None
        for account in self.config.accounts():
            if account.network == network and account.enabled and self.config.has_secrets(account):
                return account
        return None

    def mark_mention_used(self, network: str, handle: str) -> None:
        self.store.upsert_mention(
            MentionEntry(network=network, handle=handle),  # type: ignore[arg-type]
            bump_use=True,
        )

    # --- images ---

    def image_path(self, image_id: str):
        return self.config.images_dir / f"{image_id}.jpg"

    def add_image(self, draft_id: str, original_name: str, data: bytes) -> SnsImage:
        draft = self.store.get_draft(draft_id)
        processed, width, height = process_upload(data)
        image = SnsImage(
            id=uuid.uuid4().hex[:12],
            original_name=original_name,
            width=width,
            height=height,
            bytes=len(processed),
        )
        self.image_path(image.id).write_bytes(processed)
        self.store.save_image(image)
        self.store.update_draft(draft_id, image_ids=[*draft.image_ids, image.id])
        return image

    def remove_image(self, draft_id: str, image_id: str) -> SnsDraft:
        draft = self.store.get_draft(draft_id)
        return self.store.update_draft(
            draft_id, image_ids=[i for i in draft.image_ids if i != image_id]
        )

    async def generate_alt_text(self, image_id: str, lang: str) -> SnsImage:
        image = self.store.get_image(image_id)
        data = self.image_path(image_id).read_bytes()
        text = await self.ai_service.describe_image(data, "image/jpeg", lang)
        image.alt_text[lang] = text
        self.store.save_image(image)
        return image

    def set_alt_text(self, image_id: str, lang: str, text: str) -> SnsImage:
        image = self.store.get_image(image_id)
        image.alt_text[lang] = text
        self.store.save_image(image)
        return image

    def instagram_variant_path(self, image_id: str, aspect: str):
        path = self.config.images_dir / f"{image_id}-ig-{aspect}.jpg"
        if not path.exists():
            data = self.image_path(image_id).read_bytes()
            path.write_bytes(instagram_variant(data, aspect))
        return path

    def instagram_package(self, draft_id: str, aspect: str = "portrait") -> InstagramPackage:
        draft = self.store.get_draft(draft_id)
        account = next(
            (a for a in self.config.accounts() if a.network == "instagram" and a.enabled),
            None,
        )
        if account is None:
            raise ValueError("no instagram account configured")
        render = self.store.get_render(draft.id, account.id)
        caption = render.text if render else compose(draft.base_text, draft.link)
        for image_id in draft.image_ids:
            self.instagram_variant_path(image_id, aspect)
        return InstagramPackage(
            caption=caption,
            lang=render.lang if render else draft.base_lang,
            aspect=aspect,
            image_urls=[
                f"/api/social/images/{image_id}/instagram?aspect={aspect}"
                for image_id in draft.image_ids
            ],
        )
