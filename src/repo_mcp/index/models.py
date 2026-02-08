"""Typed models for indexing state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FileRecord:
    """Represents a file tracked by the index."""

    path: str
    size: int
    mtime_ns: int
    content_hash: str


@dataclass(slots=True, frozen=True)
class IndexDelta:
    """Deterministic change classification for index refresh."""

    added: tuple[str, ...]
    updated: tuple[str, ...]
    unchanged: tuple[str, ...]
    removed: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ChunkRecord:
    """Deterministic chunk metadata."""

    path: str
    start_line: int
    end_line: int
    chunk_id: str
