"""Denylist and limits policy for safe repository reads."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class SecurityLimits:
    """Runtime security limits for tool responses."""

    max_file_bytes: int = 1024 * 1024
    max_open_lines: int = 500
    max_total_bytes_per_response: int = 256 * 1024
    max_search_hits: int = 50


@dataclass(slots=True, frozen=True)
class PolicyBlockedError(Exception):
    """Raised when denylist or limits policy blocks an operation."""

    reason: str
    hint: str


def _relative_posix_path(repo_root: Path, resolved_path: Path) -> str:
    rel = resolved_path.relative_to(repo_root.resolve())
    return rel.as_posix()


def is_denylisted(repo_root: Path, resolved_path: Path) -> bool:
    """Return True when a path is denylisted by default policy."""
    rel_path = _relative_posix_path(repo_root, resolved_path)
    lowered = rel_path.lower()
    basename = Path(rel_path).name.lower()

    if basename == ".env":
        return True
    if fnmatch.fnmatch(basename, "*.pem"):
        return True
    if fnmatch.fnmatch(basename, "*.key"):
        return True
    if fnmatch.fnmatch(basename, "*.pfx"):
        return True
    if fnmatch.fnmatch(basename, "*.p12"):
        return True
    if fnmatch.fnmatch(basename, "id_rsa*"):
        return True
    if "/.git/" in f"/{lowered}/" or lowered == ".git":
        return True
    if basename.startswith("secrets."):
        return True
    return False


def enforce_file_access_policy(
    repo_root: Path,
    resolved_path: Path,
    limits: SecurityLimits,
) -> None:
    """Raise PolicyBlockedError when path or file metadata violates policy."""
    if is_denylisted(repo_root=repo_root, resolved_path=resolved_path):
        raise PolicyBlockedError(
            reason="File is denylisted by security policy.",
            hint="Use a non-sensitive file path under repo_root.",
        )

    if resolved_path.exists() and resolved_path.is_file():
        file_size = resolved_path.stat().st_size
        if file_size > limits.max_file_bytes:
            raise PolicyBlockedError(
                reason="File exceeds max_file_bytes limit.",
                hint="Request a smaller file or increase limit via approved configuration.",
            )


def enforce_open_line_limits(start_line: int, end_line: int | None, limits: SecurityLimits) -> None:
    """Raise PolicyBlockedError when requested line span exceeds max_open_lines."""
    if end_line is not None:
        requested = end_line - start_line + 1
        if requested > limits.max_open_lines:
            raise PolicyBlockedError(
                reason="Requested line range exceeds max_open_lines limit.",
                hint="Reduce the requested line range.",
            )
