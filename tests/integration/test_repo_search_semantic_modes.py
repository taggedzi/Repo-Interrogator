from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.index import manager as manager_module
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
