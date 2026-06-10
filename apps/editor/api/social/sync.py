from __future__ import annotations

import json
from pathlib import Path

from pyrage import decrypt, encrypt, x25519

from .models import NetworkRender, SnsDraft
from .store import SocialStore

BUNDLE_VERSION = 1


class SyncDisabledError(Exception):
    pass


class DraftSync:
    """Per-draft encrypted bundles (age format) committed alongside the repo.

    Each draft becomes one `{draft_id}.age` file holding the draft, its renders,
    and its translation cache. Tokens, mention cache, post history, and images
    deliberately stay in the local sqlite store. Conflicts resolve by
    `updated_at` (newer wins); identical content is never re-encrypted so files
    only change in git when the draft actually changed.
    """

    def __init__(self, store: SocialStore, drafts_dir: Path, secret_key: str | None):
        self.store = store
        self.drafts_dir = drafts_dir
        self._identity: x25519.Identity | None = None
        if secret_key:
            self._identity = x25519.Identity.from_str(secret_key.strip())

    @property
    def enabled(self) -> bool:
        return self._identity is not None

    def _ensure_enabled(self) -> x25519.Identity:
        if self._identity is None:
            raise SyncDisabledError(
                "draft sync is disabled: set BLOG_EDITOR_DRAFTS_KEY"
                " (generate one with: uv run python -m apps.editor.api.social.sync)"
            )
        return self._identity

    def _path(self, draft_id: str) -> Path:
        return self.drafts_dir / f"{draft_id}.age"

    def _bundle(self, draft_id: str) -> bytes:
        draft = self.store.get_draft(draft_id)
        bundle = {
            "version": BUNDLE_VERSION,
            "draft": draft.model_dump(),
            "renders": [
                render.model_dump() for render in self.store.get_renders(draft_id)
            ],
            "translations": self.store.get_translations(draft_id),
        }
        return json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode("utf-8")

    def export_draft(self, draft_id: str) -> bool:
        """Write the encrypted bundle; returns False when unchanged or disabled."""
        if not self.enabled:
            return False
        identity = self._ensure_enabled()
        data = self._bundle(draft_id)
        path = self._path(draft_id)
        if path.exists():
            try:
                if decrypt(path.read_bytes(), [identity]) == data:
                    return False
            except Exception:  # noqa: BLE001 - unreadable file gets rewritten
                pass
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encrypt(data, [identity.to_public()]))
        return True

    def remove_draft(self, draft_id: str) -> None:
        if self.enabled:
            self._path(draft_id).unlink(missing_ok=True)

    def export_all(self) -> int:
        exported = 0
        for draft in self.store.list_drafts(limit=10000):
            if self.export_draft(draft.id):
                exported += 1
        return exported

    def import_all(self) -> dict[str, int]:
        """Decrypt every bundle and import the ones newer than the local copy."""
        identity = self._ensure_enabled()
        counts = {"imported": 0, "skipped": 0, "errors": 0}
        for path in sorted(self.drafts_dir.glob("*.age")):
            try:
                bundle = json.loads(decrypt(path.read_bytes(), [identity]))
                draft = SnsDraft.model_validate(bundle["draft"])
            except Exception:  # noqa: BLE001 - wrong key / corrupt file
                counts["errors"] += 1
                continue
            try:
                local = self.store.get_draft(draft.id)
            except KeyError:
                local = None
            if local is not None and local.updated_at >= draft.updated_at:
                counts["skipped"] += 1
                continue
            self.store.replace_draft(draft)
            self.store.replace_renders(
                draft.id,
                [NetworkRender.model_validate(item) for item in bundle.get("renders", [])],
            )
            for item in bundle.get("translations", []):
                self.store.save_translation(
                    draft.id, item["lang"], item["source_sha256"], item["text"]
                )
            counts["imported"] += 1
        return counts

    def sync(self) -> dict[str, int]:
        counts = self.import_all()
        counts["exported"] = self.export_all()
        return counts


def main() -> None:
    """Generate a new sync key for .env."""
    identity = x25519.Identity.generate()
    print("Add this line to your .env (keep it out of the repo):")
    print(f"BLOG_EDITOR_DRAFTS_KEY={identity}")


if __name__ == "__main__":
    main()
