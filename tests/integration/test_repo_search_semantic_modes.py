from __future__ import annotations

import hashlib
import urllib.error
from pathlib import Path

import pytest
from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.index import manager as manager_module
from repo_mcp.semantic.fusion import cosine_similarity
from repo_mcp.server import create_server


def test_repo_search_semantic_mode_without_extra_returns_explicit_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)

    response = call_tool(
        server, "req-sem-1", "repo.search", {"query": "f", "mode": "semantic", "top_k": 5}
    )

    assert is_tool_error(response)


def test_repo_search_hybrid_mode_without_extra_returns_explicit_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)

    response = call_tool(
        server, "req-sem-2", "repo.search", {"query": "f", "mode": "hybrid", "top_k": 5}
    )

    assert is_tool_error(response)


def test_repo_status_reports_semantic_not_installed_when_extra_absent(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(call_tool(server, "req-status-1", "repo.status", {}))

    assert result["semantic_available"] is False
    assert result["semantic_model_status"] == "not_installed"


def test_repo_search_semantic_mode_wraps_network_download_failure_as_explicit_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: True)

    def _raise_url_error(self, *, query, top_k, filtered):
        raise urllib.error.HTTPError(
            "https://example.invalid/model.onnx", 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr(manager_module.IndexManager, "_semantic_search_hits", _raise_url_error)

    response = call_tool(
        server, "req-sem-4", "repo.search", {"query": "f", "mode": "semantic", "top_k": 5}
    )

    assert is_tool_error(response)


def test_repo_search_semantic_mode_does_not_mislabel_unrelated_os_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: True)

    def _raise_local_os_error(self, *, query, top_k, filtered):
        raise PermissionError("Permission denied: 'some_local_file.py'")

    monkeypatch.setattr(manager_module.IndexManager, "_semantic_search_hits", _raise_local_os_error)

    index_manager = server._index_manager
    try:
        index_manager.search("f", 5, mode="semantic")
    except manager_module.SemanticNotAvailableError:
        raise AssertionError(
            "an unrelated local OSError must not be reclassified as a download failure"
        ) from None
    except PermissionError:
        pass


def test_repo_search_hybrid_mode_fuses_results_when_semantic_available(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: True)
    fake_semantic_hits = [
        {
            "path": "a.py",
            "start_line": 1,
            "end_line": 2,
            "snippet": "def f():",
            "score": 0.9,
            "matched_terms": [],
        }
    ]
    monkeypatch.setattr(
        manager_module.IndexManager,
        "_semantic_search_hits",
        lambda self, *, query, top_k, filtered: fake_semantic_hits,
    )

    response = call_tool(
        server, "req-sem-3", "repo.search", {"query": "f", "mode": "hybrid", "top_k": 5}
    )

    assert not is_tool_error(response)
    result = extract_result(response)
    assert "hits" in result
    assert any(hit["path"] == "a.py" for hit in result["hits"])


class _FakeEmbedder:
    """Deterministic stand-in for the real ONNX-backed Embedder.

    Only `embed(text) -> tuple[float, ...]` is used by callers (see
    IndexManager._embed_query and VectorStore.refresh's `_EmbedderProtocol`),
    so faking just this method lets every other piece of the real wiring
    (refresh_semantic_index, VectorStore.refresh/load_vectors,
    _load_semantic_vectors, the scoping comprehension in
    _semantic_search_hits, and semantic_search's cosine ranking) execute for
    real, with real vectors written to and read back from a real temp
    data_dir.
    """

    DIM = 4

    def embed(self, text: str) -> tuple[float, ...]:
        # Fixed dimension for every input (semantic_search's cosine_similarity
        # zips query/chunk vectors with strict=True, so mismatched lengths
        # would raise). Values vary deterministically by content so the
        # resulting cosine score is not a constant/canned number.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(float(byte) / 255.0 for byte in digest[: self.DIM])


def test_repo_search_semantic_mode_runs_real_wiring_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Drives the real refresh_semantic_index -> VectorStore -> semantic_search chain.

    Unlike the other tests in this file, this does NOT stub
    `_semantic_search_hits`. Only `IndexManager._get_embedder` is faked, so
    the connected wiring chain identified in the final review (I1) actually
    runs: chunk text is read from disk, embedded, persisted to a real
    vectors.jsonl under a real temp data_dir, reloaded, scoped by path
    against the filtered search documents, and ranked by the real
    `semantic_search` cosine-similarity implementation.
    """
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: True)

    fake_embedder = _FakeEmbedder()
    monkeypatch.setattr(manager_module.IndexManager, "_get_embedder", lambda self: fake_embedder)

    index_manager = server._index_manager

    response = call_tool(
        server, "req-sem-5", "repo.search", {"query": "f", "mode": "semantic", "top_k": 5}
    )

    assert not is_tool_error(response)
    result = extract_result(response)
    hits = result["hits"]
    assert len(hits) == 1
    hit = hits[0]
    assert hit["path"] == "a.py"

    # The vector store must actually have persisted a real embedding for the
    # seeded chunk under the real data_dir -- this is the part that a
    # wholesale-stubbed test can never catch regressing.
    persisted_vectors = index_manager._load_semantic_vectors()
    assert len(persisted_vectors) == 1
    (chunk_vector,) = persisted_vectors.values()

    query_vector = fake_embedder.embed("f")
    expected_score = cosine_similarity(query_vector, chunk_vector)

    # The returned score must be the real cosine score computed by the real
    # semantic_search ranking, not a canned/hardcoded value.
    assert hit["score"] == pytest.approx(expected_score)
