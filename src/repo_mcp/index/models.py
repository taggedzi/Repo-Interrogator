"""Typed models for indexing state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FileRecord:
    """Represents a file tracked by the index."""

    path: str
    size: int
    mtime_ns: int
