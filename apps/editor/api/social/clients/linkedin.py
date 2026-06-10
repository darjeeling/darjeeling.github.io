from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from ..models import NetworkRender, PublishResult, SnsDraft, SnsImage, SocialAccount
from ..store import SocialStore
from . import SocialApiError, raise_for_status

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202506"
SCOPES = "openid profile w_member_social"
REFRESH_BUFFER = timedelta(minutes=5)

# LinkedIn "little text format": these characters must be escaped in commentary
COMMENTARY_RESERVED = "\\|{}@[]()<>#*_~"


def escape_commentary(text: str) -> str:
    for char in COMMENTARY_RESERVED:
        text = text.replace(char, f"\\{char}")
    return text


class LinkedInClient:
    def __init__(
        self,
        account: SocialAccount,
        client_id: str,
        client_secret: str,
        store: SocialStore,
        redirect_uri: str,
    ):
        self.account = account
        self.client_id = client_id
        self.client_secret = client_secret
        self.store = store
        self.redirect_uri = redirect_uri

    # --- oauth ---

    def authorize_url(self) -> str:
        state = self.store.create_oauth_state(self.account.id)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, client: httpx.AsyncClient, code: str) -> None:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
        )
        raise_for_status(response, "linkedin token exchange")
        await self._store_token(client, response.json())

    async def _store_token(self, client: httpx.AsyncClient, payload: dict) -> None:
        access_token = payload["access_token"]
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 0))
        ).isoformat()
        userinfo = await client.get(
            f"{API_BASE}/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_status(userinfo, "linkedin userinfo")
        person_urn = f"urn:li:person:{userinfo.json()['sub']}"
        self.store.save_token(
            self.account.id,
            access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            meta={"person_urn": person_urn},
        )

    async def _valid_token(self, client: httpx.AsyncClient) -> dict:
        token = self.store.get_token(self.account.id)
        if token is None:
            raise SocialApiError(f"{self.account.id} is not authorized yet")
        expires_at = token.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(UTC) + REFRESH_BUFFER:
            if not token.get("refresh_token"):
                raise SocialApiError(
                    f"{self.account.id} token expired; re-authorize from the accounts panel"
                )
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token["refresh_token"],
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            raise_for_status(response, "linkedin token refresh")
            await self._store_token(client, response.json())
            token = self.store.get_token(self.account.id)
        return token

    # --- posting ---

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def publish(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
    ) -> PublishResult:
        token = await self._valid_token(client)
        access_token = token["access_token"]
        author = token["meta"]["person_urn"]

        body: dict[str, object] = {
            "author": author,
            "commentary": escape_commentary(render.text),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        if images:
            urns = [
                (
                    await self._upload_image(client, access_token, author, data),
                    image.alt_text.get(render.lang)
                    or next(iter(image.alt_text.values()), ""),
                )
                for image, data in images
            ]
            if len(urns) == 1:
                body["content"] = {"media": {"id": urns[0][0], "altText": urns[0][1]}}
            else:
                body["content"] = {
                    "multiImage": {
                        "images": [{"id": urn, "altText": alt} for urn, alt in urns]
                    }
                }
        elif draft.link:
            body["content"] = {
                "article": {
                    "source": draft.link,
                    "title": draft.base_text.split("\n")[0][:200],
                }
            }

        response = await client.post(
            f"{API_BASE}/rest/posts", json=body, headers=self._headers(access_token)
        )
        raise_for_status(response, "linkedin post")
        post_urn = response.headers.get("x-restli-id", "")
        return PublishResult(
            account_id=self.account.id,
            ok=True,
            remote_id=post_urn,
            remote_url=f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else None,
            posted_at=datetime.now(UTC).isoformat(),
        )

    async def _upload_image(
        self, client: httpx.AsyncClient, access_token: str, author: str, data: bytes
    ) -> str:
        response = await client.post(
            f"{API_BASE}/rest/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": author}},
            headers=self._headers(access_token),
        )
        raise_for_status(response, "linkedin image init")
        value = response.json()["value"]
        upload = await client.put(
            value["uploadUrl"],
            content=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "image/jpeg",
            },
        )
        raise_for_status(upload, "linkedin image upload")
        return value["image"]
