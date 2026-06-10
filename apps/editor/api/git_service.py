from __future__ import annotations

import subprocess

from .config import EditorSettings


class GitService:
    def __init__(self, settings: EditorSettings):
        self.settings = settings

    def stage(self, paths: list[str]) -> None:
        if paths:
            self._run("add", "-A", "--", *paths)

    def unstage(self, paths: list[str]) -> None:
        if paths:
            self._run("restore", "--staged", "--", *paths)

    def commit_staged(self, message: str, paths: list[str]) -> tuple[str, str]:
        if not paths:
            raise ValueError("No paths selected for commit")
        self._ensure_no_unselected_staged_paths(paths)
        summary = self._run("commit", "-m", message, "--", *paths)
        commit_sha = self._run("rev-parse", "HEAD").strip()
        return commit_sha, summary.strip()

    def push(self, remote: str, branch: str) -> str:
        return self._run("push", remote, branch).strip()

    def is_tracked(self, path: str) -> bool:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=self.settings.repo_root,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _ensure_no_unselected_staged_paths(self, selected_paths: list[str]) -> None:
        staged = {
            line.strip()
            for line in self._run("diff", "--cached", "--name-only").splitlines()
            if line.strip()
        }
        selected = set(selected_paths)
        extra = staged - selected
        if extra:
            names = ", ".join(sorted(extra))
            raise ValueError(f"Unrelated staged files exist: {names}")

    def _run(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.settings.repo_root,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise ValueError(result.stderr.strip() or result.stdout.strip())
        return result.stdout if result.stdout else result.stderr
