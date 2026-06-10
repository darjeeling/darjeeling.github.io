from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EditorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLOG_EDITOR_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    repo_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    default_lang: str = "ko"
    host: str = "127.0.0.1"
    port: int = 8765
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BLOG_EDITOR_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BLOG_EDITOR_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
    )
    openai_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices("BLOG_EDITOR_OPENAI_MODEL", "OPENAI_MODEL"),
    )

    @property
    def content_root(self) -> Path:
        return self.repo_root / "content"

    @property
    def draft_root(self) -> Path:
        return self.content_root / "draft"

    @property
    def article_root(self) -> Path:
        return self.content_root / "articles"

    @property
    def static_root(self) -> Path:
        return self.repo_root / "apps" / "editor" / "web"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> EditorSettings:
    return EditorSettings()
