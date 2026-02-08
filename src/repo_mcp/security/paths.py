"""Path resolution helpers for repository-scoped access."""

from __future__ import annotations

from pathlib import Path


def resolve_repo_path(repo_root: Path, candidate: str) -> Path:
    """Resolve a candidate path against the repo root."""
    return (repo_root / candidate).resolve()
