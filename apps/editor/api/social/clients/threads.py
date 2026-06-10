from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from ..models import NetworkRender, PublishResult, SnsDraft, SnsImage, SocialAccount
from ..store import SocialStore
from . import SocialApiError, raise_for_status

AUTH_URL = "https://threads.net/oauth/authorize"
GRAPH_BASE = "https://graph.threads.net"
SCOPES = "threads_basic,threads_content_publish"
REFRESH_THRESHOLD = timedelta(days=7)
CONTAINER_POLL_INTERVAL = 1.0
CONTAINER_POLL_ATTEMPTS = 30
DEFAULT_REDIRECT_URI = "https://iz4u.net/threads-callback/"


class ThreadsClient:
    def __init__(
        self,
        account: SocialAccount,
        client_id: str,
        client_secret: str,
        store: SocialStore,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
    ):
        self.account = account
        self.client_id = client_id
        self.client_secret = client_secret
        self.store = store
        self.redirect_uri = redirect_uri

    # --- oauth (paste-back flow: user copies the redirected URL into the editor) ---

    def authorize_url(self) -> str:
        state = self.store.create_oauth_state(self.account.id)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    @staticmethod
    def parse_redirect(redirect_url: str) -> tuple[str, str]:
        query = parse_qs(urlparse(redirect_url).query)
        code = (query.get("code") or [""])[0].removesuffix("#_")
        state = (query.get("state") or [""])[0]
        if not code:
            raise SocialApiError("no ?code= found in the pasted URL")
        return code, state

    async def exchange_code(self, client: httpx.AsyncClient, code: str) -> None:
        response = await client.post(
            f"{GRAPH_BASE}/oauth/access_token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            },
        )
        raise_for_status(response, "threads token exchange")
        payload = response.json()
        short_token = payload["access_token"]
        user_id = str(payload["user_id"])

        long_lived = await client.get(
            f"{GRAPH_BASE}/access_token",
            params={
                "grant_type": "th_exchange_token",
                "client_secret": self.client_secret,
                "access_token": short_token,
            },
        )
        raise_for_status(long_lived, "threads long-lived token exchange")
        self._save_token(long_lived.json(), user_id)

    def _save_token(self, payload: dict, user_id: str) -> None:
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 0))
        ).isoformat()
        self.store.save_token(
            self.account.id,
            payload["access_token"],
            expires_at=expires_at,
            meta={"user_id": user_id},
        )

    async def _valid_token(self, client: httpx.AsyncClient) -> dict:
        token = self.store.get_token(self.account.id)
        if token is None:
            raise SocialApiError(f"{self.account.id} is not authorized yet")
        expires_at = token.get("expires_at")
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if expiry <= datetime.now(UTC):
                raise SocialApiError(
                    f"{self.account.id} token expired; re-authorize from the accounts panel"
                )
            if expiry <= datetime.now(UTC) + REFRESH_THRESHOLD:
                response = await client.get(
                    f"{GRAPH_BASE}/refresh_access_token",
                    params={
                        "grant_type": "th_refresh_token",
                        "access_token": token["access_token"],
                    },
                )
                if response.status_code == 200:
                    self._save_token(response.json(), token["meta"]["user_id"])
                    token = self.store.get_token(self.account.id)
        return token

    # --- publishing (text + optional link; images deliberately unsupported) ---

    async def publish(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
    ) -> PublishResult:
        token = await self._valid_token(client)
        access_token = token["access_token"]
        user_id = token["meta"]["user_id"]

        params: dict[str, str] = {
            "media_type": "TEXT",
            "text": render.text,
            "access_token": access_token,
        }
        if draft.link:
            params["link_attachment"] = draft.link
        response = await client.post(f"{GRAPH_BASE}/v1.0/{user_id}/threads", params=params)
        raise_for_status(response, "threads container create")
        creation_id = response.json()["id"]

        await self._wait_for_container(client, creation_id, access_token)

        publish = await client.post(
            f"{GRAPH_BASE}/v1.0/{user_id}/threads_publish",
            params={"creation_id": creation_id, "access_token": access_token},
        )
        raise_for_status(publish, "threads publish")
        media_id = publish.json()["id"]

        permalink = None
        info = await client.get(
            f"{GRAPH_BASE}/v1.0/{media_id}",
            params={"fields": "permalink", "access_token": access_token},
        )
        if info.status_code == 200:
            permalink = info.json().get("permalink")

        return PublishResult(
            account_id=self.account.id,
            ok=True,
            remote_id=str(media_id),
            remote_url=permalink,
            posted_at=datetime.now(UTC).isoformat(),
        )

    async def _wait_for_container(
        self, client: httpx.AsyncClient, creation_id: str, access_token: str
    ) -> None:
        for _ in range(CONTAINER_POLL_ATTEMPTS):
            response = await client.get(
                f"{GRAPH_BASE}/v1.0/{creation_id}",
                params={"fields": "status,error_message", "access_token": access_token},
            )
            if response.status_code == 200:
                status = response.json().get("status")
                if status == "FINISHED":
                    return
                if status == "ERROR":
                    raise SocialApiError(
                        f"threads container error: {response.json().get('error_message')}"
                    )
            await asyncio.sleep(CONTAINER_POLL_INTERVAL)
        raise SocialApiError("threads container did not finish processing in time")
