from __future__ import annotations

from typing import Protocol

import httpx

from ..models import NetworkRender, PublishResult, SnsDraft, SnsImage


class SocialApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SocialClient(Protocol):
    async def publish(
        self,
        client: httpx.AsyncClient,
        draft: SnsDraft,
        render: NetworkRender,
        images: list[tuple[SnsImage, bytes]],
    ) -> PublishResult: ...


def raise_for_status(response: httpx.Response, context: str) -> None:
    if response.status_code >= 400:
        raise SocialApiError(
            f"{context} failed ({response.status_code}): {response.text[:500]}",
            status_code=response.status_code,
        )
