from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ..facets import FacetSpan, build_rich_text
from ..models import MentionEntry, NetworkRender, PublishResult, SnsDraft, SnsImage, SocialAccount
from ..store import SocialStore
from . import raise_for_status


class BlueskyClient:
    def __init__(self, account: SocialAccount, app_password: str, store: SocialStore):
        self.account = account
        self.app_password = app_password
        self.store = store
        self._jwt: str | None = None
        self._did: str | None = None

    @property
    def _base(self) -> str:
        return f"{self.account.service_url}/xrpc"

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        if self._jwt:
            return
        response = await client.post(
            f"{self._base}/com.atproto.server.createSession",
            json={"identifier": self.account.handle, "password": self.app_password},
        )
        raise_for_status(response, "bluesky login")
        payload = response.json()
        self._jwt = payload["accessJwt"]
        self._did = payload["did"]

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._jwt}"}

    async def publish(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
    ) -> PublishResult:
        await self._ensure_session(client)
        text, spans = build_rich_text(render.text)
        facets = [await self._facet_from_span(client, span) for span in spans]
        facets = [f for f in facets if f is not None]

        record: dict[str, object] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "langs": [render.lang],
        }
        if facets:
            record["facets"] = facets
        if images:
            record["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [
                    {
                        "image": await self._upload_blob(client, data),
                        "alt": image.alt_text.get(render.lang)
                        or next(iter(image.alt_text.values()), ""),
                        "aspectRatio": {"width": image.width, "height": image.height},
                    }
                    for image, data in images
                ],
            }
        elif draft.link:
            record["embed"] = {
                "$type": "app.bsky.embed.external",
                "external": {
                    "uri": draft.link,
                    "title": draft.base_text.split("\n")[0][:120],
                    "description": "",
                },
            }

        response = await client.post(
            f"{self._base}/com.atproto.repo.createRecord",
            json={
                "repo": self._did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            headers=self._headers,
        )
        raise_for_status(response, "bluesky post")
        uri = response.json()["uri"]  # at://did:plc:xxx/app.bsky.feed.post/rkey
        rkey = uri.rsplit("/", 1)[-1]
        return PublishResult(
            account_id=self.account.id,
            ok=True,
            remote_id=uri,
            remote_url=f"https://bsky.app/profile/{self.account.handle}/post/{rkey}",
            posted_at=datetime.now(UTC).isoformat(),
        )

    async def _facet_from_span(
        self, client: httpx.AsyncClient, span: FacetSpan
    ) -> dict | None:
        index = {"byteStart": span.byte_start, "byteEnd": span.byte_end}
        if span.kind == "link":
            feature = {"$type": "app.bsky.richtext.facet#link", "uri": span.value}
        elif span.kind == "tag":
            feature = {"$type": "app.bsky.richtext.facet#tag", "tag": span.value}
        else:
            did = await self._resolve_handle(client, span.value)
            if did is None:
                return None  # unresolvable handle stays plain text
            feature = {"$type": "app.bsky.richtext.facet#mention", "did": did}
        return {"index": index, "features": [feature]}

    async def _resolve_handle(self, client: httpx.AsyncClient, handle: str) -> str | None:
        cached = self.store.get_mention("bluesky", f"@{handle}")
        if cached and cached.identifier:
            return cached.identifier
        response = await client.get(
            f"{self._base}/com.atproto.identity.resolveHandle",
            params={"handle": handle},
        )
        if response.status_code != 200:
            return None
        did = response.json().get("did")
        if did:
            self.store.upsert_mention(
                MentionEntry(network="bluesky", handle=f"@{handle}", identifier=did)
            )
        return did

    async def _upload_blob(self, client: httpx.AsyncClient, data: bytes) -> dict:
        response = await client.post(
            f"{self._base}/com.atproto.repo.uploadBlob",
            content=data,
            headers={**self._headers, "Content-Type": "image/jpeg"},
        )
        raise_for_status(response, "bluesky blob upload")
        return response.json()["blob"]

    async def search_people(
        self, client: httpx.AsyncClient, query: str, limit: int = 8
    ) -> list[MentionEntry]:
        await self._ensure_session(client)
        response = await client.get(
            f"{self._base}/app.bsky.actor.searchActors",
            params={"q": query, "limit": limit},
            headers=self._headers,
        )
        raise_for_status(response, "bluesky actor search")
        return [
            MentionEntry(
                network="bluesky",
                handle=f"@{actor['handle']}",
                identifier=actor.get("did", ""),
                display_name=actor.get("displayName", ""),
                avatar_url=actor.get("avatar"),
            )
            for actor in response.json().get("actors", [])
        ]
