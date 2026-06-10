from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Network = Literal["bluesky", "mastodon", "threads", "linkedin", "instagram"]
AuthStatus = Literal["ok", "needs_auth", "expired", "missing_secret"]

CHAR_LIMITS: dict[str, int] = {
    "bluesky": 300,
    "mastodon": 500,
    "threads": 500,
    "linkedin": 3000,
    "instagram": 2200,
}


class SocialAccount(BaseModel):
    id: str
    network: Network
    lang: str = "ko"
    handle: str = ""
    host: str = ""
    service_url: str = "https://bsky.social"
    mode: Literal["api", "generate_only"] = "api"
    enabled: bool = True

    @property
    def char_limit(self) -> int:
        return CHAR_LIMITS[self.network]


class AccountStatus(BaseModel):
    id: str
    network: Network
    lang: str
    handle: str
    enabled: bool
    mode: str
    char_limit: int
    auth_status: AuthStatus


class SnsImage(BaseModel):
    id: str
    original_name: str
    width: int
    height: int
    bytes: int
    alt_text: dict[str, str] = Field(default_factory=dict)


class SnsDraft(BaseModel):
    id: str
    source: Literal["standalone", "article"] = "standalone"
    article_path: str | None = None
    link: str | None = None
    base_lang: str = "ko"
    base_text: str = ""
    image_ids: list[str] = Field(default_factory=list)
    status: Literal["draft", "published", "partial"] = "draft"
    created_at: str = ""
    updated_at: str = ""


class NetworkRender(BaseModel):
    draft_id: str
    account_id: str
    lang: str
    text: str
    translated: bool = False
    manually_edited: bool = False
    count: int = 0
    limit: int = 0
    over_limit: bool = False


class PublishResult(BaseModel):
    account_id: str
    ok: bool
    remote_id: str | None = None
    remote_url: str | None = None
    error: str | None = None
    posted_at: str | None = None


class MentionEntry(BaseModel):
    network: Network
    handle: str
    identifier: str = ""
    display_name: str = ""
    avatar_url: str | None = None
    use_count: int = 0


class CreateDraftRequest(BaseModel):
    source: Literal["standalone", "article"] = "standalone"
    article_path: str | None = None
    base_lang: str = "ko"
    base_text: str = ""
    link: str | None = None


class UpdateDraftRequest(BaseModel):
    base_lang: str | None = None
    base_text: str | None = None
    link: str | None = None


class UpdateRenderRequest(BaseModel):
    text: str


class PublishRequest(BaseModel):
    account_ids: list[str]
    force: bool = False


class PublishResponse(BaseModel):
    draft_status: str
    results: list[PublishResult]


class AddPersonRequest(BaseModel):
    network: Network
    handle: str
    identifier: str = ""
    display_name: str = ""


class AltTextRequest(BaseModel):
    lang: str = "ko"
    text: str = ""


class InstagramPackage(BaseModel):
    caption: str
    lang: str
    aspect: str
    image_urls: list[str]
