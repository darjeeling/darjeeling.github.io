from __future__ import annotations

import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pelican.utils import slugify

from .config import EditorSettings
from .models import CreatePostRequest, PostDocument, PostSummary, UpdatePostRequest


FRONTMATTER_MAP = OrderedDict(
    [
        ("Title", "title"),
        ("Date", "date"),
        ("Category", "category"),
        ("Slug", "slug"),
        ("Tags", "tags"),
        ("Lang", "lang"),
        ("Summary", "summary"),
        ("Translation_Key", "translation_key"),
        ("Translation_Model", "translation_model"),
        ("Translation_At", "translation_at"),
        ("Translation_Source_Lang", "translation_source_lang"),
    ]
)


class ContentStore:
    def __init__(self, settings: EditorSettings):
        self.settings = settings

    def list_documents(self) -> list[PostSummary]:
        summaries: list[PostSummary] = []
        for kind, root in (("draft", self.settings.draft_root), ("article", self.settings.article_root)):
            if not root.exists():
                continue
            for path in sorted(self._iter_markdown_files(root)):
                doc = self.read_document(self._relative_path(path))
                summaries.append(
                    PostSummary(
                        path=doc.path,
                        kind=doc.kind,
                        title=doc.title or path.stem,
                        lang=doc.lang,
                        slug=doc.slug,
                        date=doc.date,
                        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                        translation_key=doc.translation_key,
                        tags=doc.tags,
                        suggested_commit=doc.suggested_commit,
                    )
                )
        summaries.sort(key=lambda item: (item.date, item.modified_at.isoformat()), reverse=True)
        return summaries

    def read_document(self, relative_path: str) -> PostDocument:
        path = self._resolve(relative_path)
        metadata, body_markdown = self._parse_document(path.read_text(encoding="utf-8"))
        kind = self._kind_for_path(path)
        return PostDocument(
            path=self._relative_path(path),
            kind=kind,
            title=str(metadata.get("title", "")),
            date=self._stringify_date(metadata.get("date", "")),
            category=str(metadata.get("category", "blog")),
            slug=str(metadata.get("slug", "")),
            tags=self._normalize_tags(metadata.get("tags", [])),
            lang=str(metadata.get("lang", self.settings.default_lang)),
            summary=str(metadata.get("summary", "")),
            translation_key=self._nullable_str(metadata.get("translation_key")),
            translation_model=self._nullable_str(metadata.get("translation_model")),
            translation_at=self._nullable_str(metadata.get("translation_at")),
            translation_source_lang=self._nullable_str(metadata.get("translation_source_lang")),
            body_markdown=body_markdown,
            exists=True,
            suggested_commit=not self._relative_path(path).startswith("content/draft/"),
        )

    def create_draft(self, request: CreatePostRequest) -> PostDocument:
        date_text = request.date or datetime.now().strftime("%Y-%m-%d %H:%M")
        slug_value = request.slug or self._suggest_slug(request.title, request.lang)
        filename = self._build_filename(date_text, slug_value, request.lang)
        year = self._extract_year(date_text)
        relative_path = self.settings.draft_root / year / filename
        relative_path.parent.mkdir(parents=True, exist_ok=True)
        document = PostDocument(
            path=self._relative_path(relative_path),
            kind="draft",
            title=request.title,
            date=date_text,
            category=request.category,
            slug=slug_value,
            tags=request.tags,
            lang=request.lang,
            summary=request.summary,
            translation_key=request.translation_key,
            body_markdown=request.body_markdown,
            exists=True,
            suggested_commit=False,
        )
        self.write_document(document)
        return document

    def write_document(self, document: PostDocument | UpdatePostRequest, path: str | None = None) -> PostDocument:
        source_path = self._resolve_candidate(path or document.path)

        if isinstance(document, UpdatePostRequest):
            payload = PostDocument(
                path=self._relative_path(source_path),
                kind=self._kind_for_path(source_path),
                title=document.title,
                date=document.date,
                category=document.category,
                slug=document.slug or self._suggest_slug(document.title, document.lang),
                tags=document.tags,
                lang=document.lang or self.settings.default_lang,
                summary=document.summary,
                translation_key=document.translation_key,
                translation_model=document.translation_model,
                translation_at=document.translation_at,
                translation_source_lang=document.translation_source_lang,
                body_markdown=document.body_markdown,
                exists=True,
                suggested_commit=not self._relative_path(source_path).startswith("content/draft/"),
            )
        else:
            payload = document

        target = self._desired_path(payload, current_path=source_path)
        if not self._same_location(source_path, target) and target.exists():
            raise ValueError(f"Destination already exists: {self._relative_path(target)}")
        target.parent.mkdir(parents=True, exist_ok=True)

        metadata = OrderedDict()
        for frontmatter_key, field_name in FRONTMATTER_MAP.items():
            value = getattr(payload, field_name)
            if value in (None, "", []):
                continue
            metadata[frontmatter_key] = ", ".join(value) if field_name == "tags" else value

        target.write_text(self._serialize_document(metadata, payload.body_markdown), encoding="utf-8")
        if not self._same_location(source_path, target) and source_path.exists():
            source_path.unlink()
        return self.read_document(self._relative_path(target))

    def publish(self, relative_path: str) -> PostDocument:
        document = self.read_document(relative_path)
        destination = self._target_article_path(document)
        source = self._resolve(relative_path)
        self._move_document(source, destination)
        return self.read_document(self._relative_path(destination))

    def unpublish(self, relative_path: str) -> PostDocument:
        document = self.read_document(relative_path)
        destination = self._target_draft_path(document)
        source = self._resolve(relative_path)
        self._move_document(source, destination)
        return self.read_document(self._relative_path(destination))

    def find_translation_target(self, translation_key: str, lang: str) -> PostDocument | None:
        for document in self.list_documents():
            if document.translation_key == translation_key and document.lang == lang:
                return self.read_document(document.path)
        return None

    def ensure_translation_key(self, document: PostDocument) -> PostDocument:
        if document.translation_key:
            return document
        document.translation_key = f"{self._extract_year(document.date)}-{document.slug}-{document.lang}"
        return self.write_document(document)

    def create_or_update_translation(
        self,
        source: PostDocument,
        target_lang: str,
        title: str,
        summary: str,
        body_markdown: str,
        translation_model: str,
        translation_at: str,
    ) -> PostDocument:
        source = self.ensure_translation_key(source)
        existing = self.find_translation_target(source.translation_key or "", target_lang)
        destination_doc = existing or PostDocument(
            path=self._relative_path(self._target_draft_path(source, lang=target_lang)),
            kind="draft",
            title=title,
            date=source.date,
            category=source.category,
            slug=source.slug,
            tags=source.tags,
            lang=target_lang,
            summary=summary,
            translation_key=source.translation_key,
            body_markdown=body_markdown,
            suggested_commit=False,
        )
        destination_doc.title = title
        destination_doc.date = source.date
        destination_doc.category = source.category
        destination_doc.slug = source.slug
        destination_doc.tags = source.tags
        destination_doc.lang = target_lang
        destination_doc.summary = summary
        destination_doc.translation_key = source.translation_key
        destination_doc.translation_model = translation_model
        destination_doc.translation_at = translation_at
        destination_doc.translation_source_lang = source.lang
        destination_doc.body_markdown = body_markdown
        return self.write_document(destination_doc)

    def _iter_markdown_files(self, root: Path) -> Iterable[Path]:
        for suffix in ("*.md", "*.markdown"):
            yield from root.rglob(suffix)

    def _resolve(self, relative_path: str) -> Path:
        path = self._resolve_candidate(relative_path)
        if self._repo_root() not in path.parents and path != self._repo_root():
            raise ValueError(f"Path escapes repository: {relative_path}")
        if not path.exists():
            raise FileNotFoundError(relative_path)
        return path

    def _resolve_candidate(self, relative_path: str) -> Path:
        path = (self._repo_root() / relative_path).resolve()
        if self._repo_root() not in path.parents and path != self._repo_root():
            raise ValueError(f"Path escapes repository: {relative_path}")
        return path

    def _kind_for_path(self, path: Path) -> str:
        return "draft" if self.settings.draft_root.resolve() in path.parents else "article"

    def _desired_path(self, document: PostDocument, current_path: Path | None = None) -> Path:
        if current_path is not None:
            kind = self._kind_for_path(current_path)
        else:
            kind = document.kind
        if kind == "draft":
            return self._target_draft_path(document, lang=document.lang)
        return self._target_article_path(document, lang=document.lang)

    def _move_document(self, source: Path, destination: Path) -> None:
        if self._same_location(source, destination):
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError(f"Destination already exists: {self._relative_path(destination)}")
        source.rename(destination)

    def _same_location(self, left: Path, right: Path) -> bool:
        return left.resolve() == right.resolve()

    def _repo_root(self) -> Path:
        return self.settings.repo_root.resolve()

    def _relative_path(self, path: Path) -> str:
        return str(path.resolve().relative_to(self._repo_root()))

    def _target_article_path(self, document: PostDocument, lang: str | None = None) -> Path:
        target_lang = lang or document.lang
        year = self._extract_year(document.date)
        filename = self._build_filename(document.date, document.slug, target_lang)
        return self.settings.article_root / year / filename

    def _target_draft_path(self, document: PostDocument, lang: str | None = None) -> Path:
        target_lang = lang or document.lang
        year = self._extract_year(document.date)
        filename = self._build_filename(document.date, document.slug, target_lang)
        return self.settings.draft_root / year / filename

    def _build_filename(self, date_text: str, slug_value: str, lang: str) -> str:
        prefix = self._extract_date_prefix(date_text)
        lang_suffix = "" if lang == self.settings.default_lang else f"-{lang}"
        return f"{prefix}-{slug_value}{lang_suffix}.md"

    def _extract_year(self, date_text: str) -> str:
        return self._parse_date(date_text).strftime("%Y")

    def _extract_date_prefix(self, date_text: str) -> str:
        return self._parse_date(date_text).strftime("%Y-%m-%d")

    def _parse_date(self, date_text: str) -> datetime:
        normalized = date_text.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unsupported date format: {date_text}")

    def _suggest_slug(self, title: str, lang: str) -> str:
        base = title or f"untitled-{datetime.now().strftime('%H%M%S')}"
        normalized = slugify(base, use_unicode=False)
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")

    def _normalize_tags(self, tags: str | list[str]) -> list[str]:
        if isinstance(tags, str):
            return [item.strip() for item in tags.split(",") if item.strip()]
        return [str(item).strip() for item in tags if str(item).strip()]

    def _nullable_str(self, value: object) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _stringify_date(self, value: object) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value)

    def _parse_document(self, text: str) -> tuple[dict[str, object], str]:
        lines = text.splitlines()
        metadata_lines: list[str] = []
        body_start = 0

        if lines and lines[0].strip() == "---":
            for index in range(1, len(lines)):
                if lines[index].strip() == "---":
                    metadata_lines = lines[1:index]
                    body_start = index + 1
                    break
        else:
            for index, line in enumerate(lines):
                if not line.strip():
                    body_start = index + 1
                    break
                if ":" not in line:
                    body_start = index
                    break
                metadata_lines.append(line)
            else:
                body_start = len(lines)

        metadata: dict[str, object] = {}
        for line in metadata_lines:
            if ":" not in line:
                continue
            key, value = line.split(":", maxsplit=1)
            metadata[key.strip().lower()] = value.strip()

        body = "\n".join(lines[body_start:]).lstrip("\n")
        return metadata, body

    def _serialize_document(self, metadata: OrderedDict[str, object], body_markdown: str) -> str:
        metadata_block = "\n".join(f"{key}: {value}" for key, value in metadata.items())
        content = body_markdown.rstrip()
        return f"---\n{metadata_block}\n---\n\n{content}\n"
