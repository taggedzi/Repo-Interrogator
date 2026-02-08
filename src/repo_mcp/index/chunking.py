"""Deterministic line-based chunking with stable chunk IDs."""

from __future__ import annotations

import hashlib

from repo_mcp.index.models import ChunkRecord

DEFAULT_CHUNK_LINES = 200
DEFAULT_CHUNK_OVERLAP_LINES = 30


def chunk_text(
    path: str,
    text: str,
    chunk_lines: int = DEFAULT_CHUNK_LINES,
    overlap_lines: int = DEFAULT_CHUNK_OVERLAP_LINES,
) -> list[ChunkRecord]:
    """Split text into deterministic line chunks with overlap."""
    if chunk_lines < 1:
        raise ValueError("chunk_lines must be >= 1")
    if overlap_lines < 0:
        raise ValueError("overlap_lines must be >= 0")
    if overlap_lines >= chunk_lines:
        raise ValueError("overlap_lines must be less than chunk_lines")

    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[ChunkRecord] = []
    step = chunk_lines - overlap_lines
    start_index = 0
    while start_index < len(lines):
        end_index_exclusive = min(start_index + chunk_lines, len(lines))
        start_line = start_index + 1
        end_line = end_index_exclusive
        chunk_lines_text = lines[start_index:end_index_exclusive]
        chunk_id = build_chunk_id(path, start_line, end_line, chunk_lines_text)
        chunks.append(
            ChunkRecord(
                path=path,
                start_line=start_line,
                end_line=end_line,
                chunk_id=chunk_id,
            )
        )
        if end_index_exclusive == len(lines):
            break
        start_index += step
    return chunks


def build_chunk_id(path: str, start_line: int, end_line: int, lines: list[str]) -> str:
    """Build a stable chunk identifier from deterministic inputs."""
    payload = "\n".join(lines)
    digest = hashlib.sha256()
    digest.update(path.encode("utf-8"))
    digest.update(b"|")
    digest.update(str(start_line).encode("ascii"))
    digest.update(b"|")
    digest.update(str(end_line).encode("ascii"))
    digest.update(b"|")
    digest.update(payload.encode("utf-8"))
    return digest.hexdigest()
