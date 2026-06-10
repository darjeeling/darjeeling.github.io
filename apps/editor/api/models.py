from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PostDocument(BaseModel):
    path: str
    kind: Literal["draft", "article"]
    title: str = ""
    date: str = ""
    category: str = "blog"
    slug: str = ""
    tags: list[str] = Field(default_factory=list)
    lang: str = "ko"
    summary: str = ""
    translation_key: str | None = None
    translation_model: str | None = None
    translation_at: str | None = None
    translation_source_lang: str | None = None
    body_markdown: str = ""
    exists: bool = True
    suggested_commit: bool = True


class PostSummary(BaseModel):
    path: str
    kind: Literal["draft", "article"]
    title: str
    lang: str
    slug: str
    date: str
    modified_at: datetime
    translation_key: str | None = None
    tags: list[str] = Field(default_factory=list)
    suggested_commit: bool = True


class CreatePostRequest(BaseModel):
    title: str = ""
    lang: str = "ko"
    category: str = "blog"
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    body_markdown: str = ""
    date: str = ""
    slug: str = ""
    translation_key: str | None = None


class UpdatePostRequest(BaseModel):
    title: str
    date: str
    category: str
    slug: str
    tags: list[str]
    lang: str
    summary: str
    translation_key: str | None = None
    translation_model: str | None = None
    translation_at: str | None = None
    translation_source_lang: str | None = None
    body_markdown: str


class PreviewRequest(BaseModel):
    body_markdown: str
    translation_model: str | None = None
    translation_at: str | None = None
    translation_source_lang: str | None = None


class PreviewResponse(BaseModel):
    body_html: str
    provenance_html: str | None = None


class PublishResponse(BaseModel):
    document: PostDocument
    commit_sha: str
    commit_summary: str
    push_summary: str
    build_summary: str


class SimpleValueResponse(BaseModel):
    value: str


class SuggestionsResponse(BaseModel):
    values: list[str]


class TranslateRequest(BaseModel):
    source_path: str
    target_lang: str


class ConfigResponse(BaseModel):
    default_lang: str
    draft_root: str
    article_root: str
    ai_enabled: bool
    openai_model: str
