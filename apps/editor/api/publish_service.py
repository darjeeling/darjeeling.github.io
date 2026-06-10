from __future__ import annotations

import subprocess

from .config import EditorSettings
from .content_store import ContentStore
from .git_service import GitService
from .models import PostDocument, PublishResponse


class PublishService:
    def __init__(self, settings: EditorSettings, store: ContentStore, git_service: GitService):
        self.settings = settings
        self.store = store
        self.git_service = git_service

    def publish(self, draft_path: str) -> PublishResponse:
        draft_document = self.store.read_document(draft_path)
        if draft_document.kind != "draft":
            raise ValueError("Only draft posts can be published from the editor.")

        staged_paths = [draft_document.path] if self.git_service.is_tracked(draft_document.path) else []
        published_document = self.store.publish(draft_document.path)
        commit_sha: str | None = None
        staged_paths.append(published_document.path)

        try:
            build_summary = self._build_site()
            self.git_service.stage(staged_paths)
            commit_message = self._commit_message(published_document)
            commit_sha, commit_summary = self.git_service.commit_staged(commit_message, staged_paths)
            push_summary = self.git_service.push("origin", "main")
        except Exception as exc:  # noqa: BLE001
            if commit_sha is None:
                rollback_error = self._rollback_publish(published_document.path, staged_paths)
                if rollback_error:
                    raise ValueError(f"{exc}\n\nRollback problem:\n{rollback_error}") from exc
            raise ValueError(str(exc)) from exc

        return PublishResponse(
            document=published_document,
            commit_sha=commit_sha,
            commit_summary=commit_summary,
            push_summary=push_summary,
            build_summary=build_summary,
        )

    def _build_site(self) -> str:
        result = subprocess.run(
            ["uv", "run", "pelican", "content", "-o", "output", "-s", "publishconf.py"],
            cwd=self.settings.repo_root,
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            raise ValueError(f"Publish build failed.\n\n{output}")
        return output or "Production build succeeded."

    def _commit_message(self, document: PostDocument) -> str:
        title = document.title.strip() or document.slug
        return f"Publish {document.lang} post: {title}"

    def _rollback_publish(self, published_path: str, staged_paths: list[str]) -> str | None:
        rollback_errors: list[str] = []
        try:
            self.git_service.unstage(staged_paths)
        except Exception as exc:  # noqa: BLE001
            rollback_errors.append(f"unstage failed: {exc}")
        try:
            self.store.unpublish(published_path)
        except Exception as exc:  # noqa: BLE001
            rollback_errors.append(f"rollback failed: {exc}")
        if rollback_errors:
            return "\n".join(rollback_errors)
        return None
