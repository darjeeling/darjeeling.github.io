from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values

from ..config import EditorSettings
from .models import SocialAccount

SECRET_KEYS: dict[str, list[str]] = {
    "bluesky": ["APP_PASSWORD"],
    "mastodon": ["ACCESS_TOKEN"],
    "threads": ["CLIENT_ID", "CLIENT_SECRET"],
    "linkedin": ["CLIENT_ID", "CLIENT_SECRET"],
    "instagram": [],
}


class SocialConfig:
    """Account list from social_accounts.json plus secrets from env / .env."""

    def __init__(self, settings: EditorSettings):
        self.settings = settings
        self._env = self._load_env()

    @property
    def accounts_path(self) -> Path:
        return self.settings.repo_root / "apps" / "editor" / "social_accounts.json"

    @property
    def data_dir(self) -> Path:
        path = self.settings.repo_root / "apps" / "editor" / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "social.db"

    @property
    def images_dir(self) -> Path:
        path = self.data_dir / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def drafts_dir(self) -> Path:
        """Encrypted draft bundles, committed to the repo (unlike data_dir)."""
        path = self.settings.repo_root / "apps" / "editor" / "drafts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def drafts_key(self) -> str | None:
        return self._env.get("BLOG_EDITOR_DRAFTS_KEY")

    def _load_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        env_file = self.settings.repo_root / ".env"
        if env_file.exists():
            env.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
        env.update(os.environ)
        return env

    def accounts(self) -> list[SocialAccount]:
        if not self.accounts_path.exists():
            return []
        raw = json.loads(self.accounts_path.read_text(encoding="utf-8"))
        return [SocialAccount.model_validate(item) for item in raw]

    def account(self, account_id: str) -> SocialAccount:
        for account in self.accounts():
            if account.id == account_id:
                return account
        raise KeyError(f"unknown social account: {account_id}")

    def secret(self, account_id: str, key: str) -> str | None:
        env_key = f"BLOG_EDITOR_SNS_{account_id.upper().replace('-', '_')}_{key}"
        return self._env.get(env_key)

    def has_secrets(self, account: SocialAccount) -> bool:
        return all(self.secret(account.id, key) for key in SECRET_KEYS[account.network])
