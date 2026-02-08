"""Path resolution helpers for repository-scoped access."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

WINDOWS_ABSOLUTE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z]:[\\/]")


class PathBlockedError(Exception):
    """Raised when a requested path violates sandbox policy."""

    def __init__(self, reason: str, hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint


def _normalize_relative_input(candidate: str) -> tuple[str, bool]:
    """Normalize path separators and detect absolute-style inputs."""
    normalized = candidate.replace("\\", "/")
    if normalized.startswith("/"):
        return normalized, True
    if WINDOWS_ABSOLUTE_PATTERN.match(normalized):
        return normalized, True
    return normalized, False


def resolve_repo_path(repo_root: Path, candidate: str) -> Path:
    """Resolve a candidate path against the repo root with sandbox enforcement."""
    root = repo_root.resolve()
    normalized, is_absolute_style = _normalize_relative_input(candidate)

    if not normalized:
        raise PathBlockedError(
            reason="Path is empty.",
            hint="Provide a repository-relative path such as 'src/module.py'.",
        )

    if is_absolute_style:
        resolved_absolute = Path(normalized).resolve(strict=False)
        if not resolved_absolute.is_relative_to(root):
            raise PathBlockedError(
                reason="Absolute path is outside repo_root.",
                hint="Use a path located under the configured repository root.",
            )
        return resolved_absolute

    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise PathBlockedError(
            reason="Path traversal is blocked.",
            hint="Remove '..' segments and use a repository-relative path.",
        )

    resolved = (root / Path(*parts)).resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise PathBlockedError(
            reason="Resolved path escapes repo_root.",
            hint="Use a path located under the configured repository root.",
        )
    return resolved
