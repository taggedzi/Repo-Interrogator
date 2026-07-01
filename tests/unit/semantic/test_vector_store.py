from __future__ import annotations

from pathlib import Path

from repo_mcp.index.models import ChunkRecord
from repo_mcp.semantic.vector_store import VectorStore


class _FakeEmbedder:
    def __init__(self) -> None:
        self.embed_calls: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.embed_calls.append(text)
        return (float(len(text)), 0.0, 0.0)


def _chunk(chunk_id: str, path: str = "a.py") -> ChunkRecord:
    return ChunkRecord(path=path, start_line=1, end_line=1, chunk_id=chunk_id)


def test_vector_store_refresh_embeds_new_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    chunks = [_chunk("id-1"), _chunk("id-2")]

    result = store.refresh(
        chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder
    )

    assert result.embedded == 2
    assert result.reused == 0
    assert result.removed == 0
    assert sorted(embedder.embed_calls) == ["text-id-1", "text-id-2"]

    vectors = store.load_vectors()
    assert set(vectors.keys()) == {"id-1", "id-2"}


def test_vector_store_refresh_reuses_unchanged_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    chunks = [_chunk("id-1")]
    store.refresh(chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder)

    embedder.embed_calls.clear()
    result = store.refresh(
        chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder
    )

    assert result.embedded == 0
    assert result.reused == 1
    assert embedder.embed_calls == []


def test_vector_store_refresh_removes_stale_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    store.refresh(
        [_chunk("id-1"), _chunk("id-2")],
        read_chunk_text=lambda c: f"text-{c.chunk_id}",
        embedder=embedder,
    )

    result = store.refresh(
        [_chunk("id-1")],
        read_chunk_text=lambda c: f"text-{c.chunk_id}",
        embedder=embedder,
    )

    assert result.removed == 1
    assert set(store.load_vectors().keys()) == {"id-1"}


def test_vector_store_refresh_skips_chunk_on_embedding_failure(tmp_path: Path) -> None:
    class _FailingEmbedder:
        def embed(self, text: str) -> tuple[float, ...]:
            if text == "text-id-bad":
                raise RuntimeError("inference failed")
            return (1.0, 0.0, 0.0)

    store = VectorStore(data_dir=tmp_path)
    chunks = [_chunk("id-good"), _chunk("id-bad")]

    result = store.refresh(
        chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=_FailingEmbedder()
    )

    assert result.embedded == 1
    assert result.failed == 1
    assert set(store.load_vectors().keys()) == {"id-good"}


def test_vector_store_persists_across_instances(tmp_path: Path) -> None:
    embedder = _FakeEmbedder()
    VectorStore(data_dir=tmp_path).refresh(
        [_chunk("id-1")], read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder
    )

    reloaded = VectorStore(data_dir=tmp_path)
    vectors = reloaded.load_vectors()

    assert vectors["id-1"] == (float(len("text-id-1")), 0.0, 0.0)
