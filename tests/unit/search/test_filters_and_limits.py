from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.security import SecurityLimits
from repo_mcp.server import create_server


def test_search_file_glob_and_path_prefix_filters(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "main.py").write_text("keyword alpha\n", encoding="utf-8")
    (tmp_path / "docs" / "notes.md").write_text("keyword docs\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-filter-1", "repo.refresh_index", {})

    by_glob = call_tool(
        server,
        "req-filter-2",
        "repo.search",
        {"query": "keyword", "mode": "bm25", "file_glob": "src/*.py", "top_k": 10},
    )
    by_prefix = call_tool(
        server,
        "req-filter-3",
        "repo.search",
        {"query": "keyword", "mode": "bm25", "path_prefix": "docs/", "top_k": 10},
    )

    assert [hit["path"] for hit in extract_result(by_glob)["hits"]] == ["src/main.py"]
    assert [hit["path"] for hit in extract_result(by_prefix)["hits"]] == ["docs/notes.md"]


def test_search_limits_enforced_and_top_k_bounded(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    for idx in range(1, 6):
        (tmp_path / "src" / f"f{idx}.py").write_text(f"keyword item {idx}\n", encoding="utf-8")

    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_search_hits=3))
    call_tool(server, "req-limit-1", "repo.refresh_index", {})

    blocked = call_tool(
        server, "req-limit-2", "repo.search", {"query": "keyword", "mode": "bm25", "top_k": 10}
    )
    assert is_tool_error(blocked)

    allowed = call_tool(
        server, "req-limit-3", "repo.search", {"query": "keyword", "mode": "bm25", "top_k": 2}
    )
    assert not is_tool_error(allowed)
    assert len(extract_result(allowed)["hits"]) == 2
