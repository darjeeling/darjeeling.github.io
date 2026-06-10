from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import MentionEntry, NetworkRender, PublishResult, SnsDraft, SnsImage

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    article_path TEXT,
    link TEXT,
    base_lang TEXT NOT NULL,
    base_text TEXT NOT NULL,
    image_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS renders (
    draft_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    text TEXT NOT NULL,
    translated INTEGER NOT NULL DEFAULT 0,
    manually_edited INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (draft_id, account_id)
);
CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    bytes INTEGER NOT NULL,
    alt_text TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS post_history (
    draft_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    remote_id TEXT,
    remote_url TEXT,
    posted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentions (
    network TEXT NOT NULL,
    handle TEXT NOT NULL,
    identifier TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    avatar_url TEXT,
    use_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    PRIMARY KEY (network, handle)
);
CREATE TABLE IF NOT EXISTS oauth_tokens (
    key TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TEXT,
    meta_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS translations (
    draft_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (draft_id, lang, source_sha256)
);
CREATE TABLE IF NOT EXISTS oauth_states (
    state TEXT PRIMARY KEY,
    network TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SocialStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE drafts ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE drafts SET updated_at = created_at WHERE updated_at = ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- drafts ---

    def create_draft(
        self,
        *,
        source: str,
        base_lang: str,
        base_text: str,
        article_path: str | None = None,
        link: str | None = None,
    ) -> SnsDraft:
        now = _now()
        draft = SnsDraft(
            id=uuid.uuid4().hex[:12],
            source=source,  # type: ignore[arg-type]
            article_path=article_path,
            link=link,
            base_lang=base_lang,
            base_text=base_text,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO drafts (id, source, article_path, link, base_lang, base_text,"
                " image_ids, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    draft.id,
                    draft.source,
                    draft.article_path,
                    draft.link,
                    draft.base_lang,
                    draft.base_text,
                    json.dumps(draft.image_ids),
                    draft.status,
                    draft.created_at,
                    draft.updated_at,
                ),
            )
        return draft

    def get_draft(self, draft_id: str) -> SnsDraft:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown draft: {draft_id}")
        return self._draft_from_row(row)

    def list_drafts(self, limit: int = 50) -> list[SnsDraft]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._draft_from_row(row) for row in rows]

    def update_draft(self, draft_id: str, **fields: object) -> SnsDraft:
        allowed = {"base_lang", "base_text", "link", "status", "image_ids"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if updates:
            if "image_ids" in updates:
                updates["image_ids"] = json.dumps(updates["image_ids"])
            updates["updated_at"] = _now()
            sets = ", ".join(f"{k} = ?" for k in updates)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE drafts SET {sets} WHERE id = ?",
                    (*updates.values(), draft_id),
                )
        return self.get_draft(draft_id)

    def delete_draft(self, draft_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.execute("DELETE FROM renders WHERE draft_id = ?", (draft_id,))
            conn.execute("DELETE FROM translations WHERE draft_id = ?", (draft_id,))

    def _draft_from_row(self, row: sqlite3.Row) -> SnsDraft:
        return SnsDraft(
            id=row["id"],
            source=row["source"],
            article_path=row["article_path"],
            link=row["link"],
            base_lang=row["base_lang"],
            base_text=row["base_text"],
            image_ids=json.loads(row["image_ids"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def touch_draft(self, draft_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET updated_at = ? WHERE id = ?", (_now(), draft_id)
            )

    def replace_draft(self, draft: SnsDraft) -> None:
        """Insert or overwrite a draft verbatim (sync import: timestamps preserved)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO drafts (id, source, article_path, link, base_lang,"
                " base_text, image_ids, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    draft.id,
                    draft.source,
                    draft.article_path,
                    draft.link,
                    draft.base_lang,
                    draft.base_text,
                    json.dumps(draft.image_ids),
                    draft.status,
                    draft.created_at,
                    draft.updated_at,
                ),
            )

    def replace_renders(self, draft_id: str, renders: list[NetworkRender]) -> None:
        """Replace all renders for a draft without touching updated_at (sync import)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM renders WHERE draft_id = ?", (draft_id,))
            for render in renders:
                conn.execute(
                    "INSERT INTO renders (draft_id, account_id, lang, text, translated,"
                    " manually_edited) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        draft_id,
                        render.account_id,
                        render.lang,
                        render.text,
                        int(render.translated),
                        int(render.manually_edited),
                    ),
                )

    # --- renders ---

    def upsert_render(self, render: NetworkRender) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO renders (draft_id, account_id, lang, text, translated, manually_edited)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(draft_id, account_id) DO UPDATE SET"
                " lang = excluded.lang, text = excluded.text,"
                " translated = excluded.translated, manually_edited = excluded.manually_edited",
                (
                    render.draft_id,
                    render.account_id,
                    render.lang,
                    render.text,
                    int(render.translated),
                    int(render.manually_edited),
                ),
            )
            conn.execute(
                "UPDATE drafts SET updated_at = ? WHERE id = ?",
                (_now(), render.draft_id),
            )

    def get_renders(self, draft_id: str) -> list[NetworkRender]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM renders WHERE draft_id = ?", (draft_id,)
            ).fetchall()
        return [
            NetworkRender(
                draft_id=row["draft_id"],
                account_id=row["account_id"],
                lang=row["lang"],
                text=row["text"],
                translated=bool(row["translated"]),
                manually_edited=bool(row["manually_edited"]),
            )
            for row in rows
        ]

    def get_render(self, draft_id: str, account_id: str) -> NetworkRender | None:
        for render in self.get_renders(draft_id):
            if render.account_id == account_id:
                return render
        return None

    # --- images ---

    def save_image(self, image: SnsImage) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO images (id, original_name, width, height, bytes, alt_text)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    image.id,
                    image.original_name,
                    image.width,
                    image.height,
                    image.bytes,
                    json.dumps(image.alt_text),
                ),
            )

    def get_image(self, image_id: str) -> SnsImage:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown image: {image_id}")
        return SnsImage(
            id=row["id"],
            original_name=row["original_name"],
            width=row["width"],
            height=row["height"],
            bytes=row["bytes"],
            alt_text=json.loads(row["alt_text"]),
        )

    # --- post history / idempotency ---

    def was_posted(self, draft_id: str, account_id: str, content_sha256: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM post_history WHERE draft_id = ? AND account_id = ?"
                " AND content_sha256 = ? LIMIT 1",
                (draft_id, account_id, content_sha256),
            ).fetchone()
        return row is not None

    def record_post(
        self, draft_id: str, account_id: str, content_sha256: str, result: PublishResult
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO post_history (draft_id, account_id, content_sha256,"
                " remote_id, remote_url, posted_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    draft_id,
                    account_id,
                    content_sha256,
                    result.remote_id,
                    result.remote_url,
                    result.posted_at or _now(),
                ),
            )

    def post_history(self, draft_id: str) -> list[PublishResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM post_history WHERE draft_id = ? ORDER BY posted_at",
                (draft_id,),
            ).fetchall()
        return [
            PublishResult(
                account_id=row["account_id"],
                ok=True,
                remote_id=row["remote_id"],
                remote_url=row["remote_url"],
                posted_at=row["posted_at"],
            )
            for row in rows
        ]

    # --- mentions ---

    def search_mentions(self, network: str, query: str, limit: int = 10) -> list[MentionEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mentions WHERE network = ?"
                " AND (handle LIKE ? OR display_name LIKE ?)"
                " ORDER BY use_count DESC LIMIT ?",
                (network, f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [self._mention_from_row(row) for row in rows]

    def upsert_mention(self, entry: MentionEntry, *, bump_use: bool = False) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO mentions (network, handle, identifier, display_name, avatar_url,"
                " use_count, last_used_at) VALUES (?, ?, ?, ?, ?, 0, NULL)"
                " ON CONFLICT(network, handle) DO UPDATE SET"
                " identifier = CASE WHEN excluded.identifier != '' THEN excluded.identifier"
                "   ELSE mentions.identifier END,"
                " display_name = CASE WHEN excluded.display_name != '' THEN excluded.display_name"
                "   ELSE mentions.display_name END,"
                " avatar_url = COALESCE(excluded.avatar_url, mentions.avatar_url)",
                (
                    entry.network,
                    entry.handle,
                    entry.identifier,
                    entry.display_name,
                    entry.avatar_url,
                ),
            )
            if bump_use:
                conn.execute(
                    "UPDATE mentions SET use_count = use_count + 1, last_used_at = ?"
                    " WHERE network = ? AND handle = ?",
                    (_now(), entry.network, entry.handle),
                )

    def get_mention(self, network: str, handle: str) -> MentionEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mentions WHERE network = ? AND handle = ?",
                (network, handle),
            ).fetchone()
        return self._mention_from_row(row) if row else None

    def _mention_from_row(self, row: sqlite3.Row) -> MentionEntry:
        return MentionEntry(
            network=row["network"],
            handle=row["handle"],
            identifier=row["identifier"],
            display_name=row["display_name"],
            avatar_url=row["avatar_url"],
            use_count=row["use_count"],
        )

    # --- oauth tokens ---

    def save_token(
        self,
        key: str,
        access_token: str,
        *,
        refresh_token: str | None = None,
        expires_at: str | None = None,
        meta: dict | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO oauth_tokens (key, access_token, refresh_token,"
                " expires_at, meta_json) VALUES (?, ?, ?, ?, ?)",
                (key, access_token, refresh_token, expires_at, json.dumps(meta or {})),
            )

    def get_token(self, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM oauth_tokens WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return {
            "access_token": row["access_token"],
            "refresh_token": row["refresh_token"],
            "expires_at": row["expires_at"],
            "meta": json.loads(row["meta_json"]),
        }

    # --- oauth state (CSRF) ---

    def create_oauth_state(self, account_id: str) -> str:
        state = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oauth_states (state, network, created_at) VALUES (?, ?, ?)",
                (state, account_id, _now()),
            )
        return state

    def consume_oauth_state(self, state: str) -> str | None:
        """Validate and remove a state token, returning the account id it was issued for."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT network FROM oauth_states WHERE state = ?", (state,)
            ).fetchone()
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return row["network"] if row else None

    # --- translation cache ---

    def get_translations(self, draft_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT lang, source_sha256, text FROM translations WHERE draft_id = ?"
                " ORDER BY lang, source_sha256",
                (draft_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_translation(self, draft_id: str, lang: str, source_sha256: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT text FROM translations WHERE draft_id = ? AND lang = ?"
                " AND source_sha256 = ?",
                (draft_id, lang, source_sha256),
            ).fetchone()
        return row["text"] if row else None

    def save_translation(self, draft_id: str, lang: str, source_sha256: str, text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO translations (draft_id, lang, source_sha256, text)"
                " VALUES (?, ?, ?, ?)",
                (draft_id, lang, source_sha256, text),
            )
