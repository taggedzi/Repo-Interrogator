"""Sidecar vector store for chunk embeddings, incrementally refreshed by chunk_id."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from repo_mcp.index.models import ChunkRecord


class _EmbedderProtocol(Protocol):
    def embed(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True, slots=True)
class VectorRefreshResult:
    embedded: int
    reused: int
    removed: int
    failed: int


class VectorStore:
    """Persists chunk_id -> embedding vector, keyed off the existing content-hash chunk_id."""

    def __init__(self, data_dir: Path) -> None:
        self._vectors_path = data_dir / "semantic_index" / "vectors.jsonl"

    def refresh(
        self,
        chunks: list[ChunkRecord],
        *,
        read_chunk_text: Callable[[ChunkRecord], str],
        embedder: _EmbedderProtocol,
    ) -> VectorRefreshResult:
        """Embed any chunk_id not already stored, drop chunk_ids no longer present."""
        existing = self.load_vectors()
        current_ids = {chunk.chunk_id for chunk in chunks}
        embedded = 0
        reused = 0
        failed = 0
        updated: dict[str, tuple[float, ...]] = {}
        for chunk in sorted(chunks, key=lambda item: item.chunk_id):
            if chunk.chunk_id in existing:
                updated[chunk.chunk_id] = existing[chunk.chunk_id]
                reused += 1
                continue
            try:
                vector = embedder.embed(read_chunk_text(chunk))
            except Exception:
                # A single chunk's embedding failure (e.g. a transient ONNX
                # runtime error) must not abort the whole refresh or take down
                # semantic search for every other chunk. The chunk is simply
                # left out of the vector store and re-attempted on the next
                # refresh, since it won't be in `existing` next time either.
                failed += 1
                continue
            updated[chunk.chunk_id] = vector
            embedded += 1
        removed = len(set(existing.keys()) - current_ids)
        self._write_vectors(updated)
        return VectorRefreshResult(embedded=embedded, reused=reused, removed=removed, failed=failed)

    def load_vectors(self) -> dict[str, tuple[float, ...]]:
        """Return all currently stored chunk_id -> vector pairs."""
        if not self._vectors_path.exists():
            return {}
        vectors: dict[str, tuple[float, ...]] = {}
        with self._vectors_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                chunk_id = obj.get("chunk_id")
                vector = obj.get("vector")
                if not isinstance(chunk_id, str) or not isinstance(vector, list):
                    continue
                vectors[chunk_id] = tuple(float(value) for value in vector)
        return vectors

    def _write_vectors(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._vectors_path.with_suffix(".jsonl.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for chunk_id in sorted(vectors.keys()):
                row = {"chunk_id": chunk_id, "vector": list(vectors[chunk_id])}
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")
        tmp_path.replace(self._vectors_path)
