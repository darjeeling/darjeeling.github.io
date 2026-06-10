from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from ..models import MentionEntry, NetworkRender, PublishResult, SnsDraft, SnsImage, SocialAccount
from . import raise_for_status

MEDIA_POLL_INTERVAL = 0.3
MEDIA_POLL_ATTEMPTS = 30


class MastodonClient:
    def __init__(self, account: SocialAccount, access_token: str):
        self.account = account
        self.access_token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def publish(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
        *,
        idempotency_key: str,
    ) -> PublishResult:
        media_ids = [
            await self._upload_media(client, image, data, render.lang)
            for image, data in images
        ]
        data: dict[str, object] = {
            "status": render.text,
            "language": render.lang,
        }
        if media_ids:
            data["media_ids[]"] = media_ids
        response = await client.post(
            f"{self.account.host}/api/v1/statuses",
            data=data,
            headers={**self._headers, "Idempotency-Key": idempotency_key},
        )
        raise_for_status(response, "mastodon post")
        payload = response.json()
        return PublishResult(
            account_id=self.account.id,
            ok=True,
            remote_id=str(payload.get("id", "")),
            remote_url=payload.get("url"),
            posted_at=datetime.now(UTC).isoformat(),
        )

    async def _upload_media(
        self,
        client: httpx.AsyncClient,
        image: SnsImage,
        data: bytes,
        lang: str,
    ) -> str:
        description = image.alt_text.get(lang) or next(iter(image.alt_text.values()), "")
        response = await client.post(
            f"{self.account.host}/api/v2/media",
            files={"file": (image.original_name, data, "image/jpeg")},
            data={"description": description} if description else {},
            headers=self._headers,
        )
        raise_for_status(response, "mastodon media upload")
        media_id = str(response.json()["id"])
        if response.status_code == 202:
            await self._wait_for_media(client, media_id)
        return media_id

    async def _wait_for_media(self, client: httpx.AsyncClient, media_id: str) -> None:
        for _ in range(MEDIA_POLL_ATTEMPTS):
            response = await client.get(
                f"{self.account.host}/api/v1/media/{media_id}", headers=self._headers
            )
            if response.status_code == 200:
                return
            await asyncio.sleep(MEDIA_POLL_INTERVAL)
        raise_for_status(response, "mastodon media processing")

    async def search_people(
        self, client: httpx.AsyncClient, query: str, limit: int = 8
    ) -> list[MentionEntry]:
        response = await client.get(
            f"{self.account.host}/api/v2/search",
            params={"q": query, "type": "accounts", "resolve": "true", "limit": limit},
            headers=self._headers,
        )
        raise_for_status(response, "mastodon account search")
        results = response.json().get("accounts", [])
        return [
            MentionEntry(
                network="mastodon",
                handle=f"@{item['acct']}",
                identifier=str(item.get("id", "")),
                display_name=item.get("display_name", ""),
                avatar_url=item.get("avatar"),
            )
            for item in results
        ]
