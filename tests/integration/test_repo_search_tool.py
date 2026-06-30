from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_repo_search_tool_returns_structured_hits(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "api.py").write_text(
        "def endpoint():\n    return 'token parser'\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "worker.py").write_text(
        "def worker():\n    return 'queue parser'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-s-1", "repo.refresh_index", {})

    result = extract_result(
        call_tool(
            server,
            "req-s-2",
            "repo.search",
            {"query": "parser", "mode": "bm25", "top_k": 5, "file_glob": "pkg/*.py"},
        )
    )

    hits = result["hits"]
    assert len(hits) == 2
    for hit in hits:
        assert set(hit.keys()) == {
            "path",
            "start_line",
            "end_line",
            "snippet",
            "score",
            "matched_terms",
        }
        assert isinstance(hit["path"], str)
        assert isinstance(hit["start_line"], int)
        assert isinstance(hit["end_line"], int)
        assert isinstance(hit["snippet"], str)
        assert isinstance(hit["score"], float)
        assert isinstance(hit["matched_terms"], list)
