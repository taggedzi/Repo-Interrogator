from __future__ import annotations

from pathlib import Path

from repo_mcp.security import SecurityLimits
from repo_mcp.server import create_server


def test_search_file_glob_and_path_prefix_filters(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "main.py").write_text("keyword alpha\n", encoding="utf-8")
    (tmp_path / "docs" / "notes.md").write_text("keyword docs\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-filter-1", "method": "repo.refresh_index", "params": {}})

    by_glob = server.handle_payload(
        {
            "id": "req-filter-2",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "file_glob": "src/*.py", "top_k": 10},
        }
    )
    by_prefix = server.handle_payload(
        {
            "id": "req-filter-3",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "path_prefix": "docs/", "top_k": 10},
        }
    )

    assert [hit["path"] for hit in by_glob["result"]["hits"]] == ["src/main.py"]
    assert [hit["path"] for hit in by_prefix["result"]["hits"]] == ["docs/notes.md"]


def test_search_limits_enforced_and_top_k_bounded(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    for idx in range(1, 6):
        (tmp_path / "src" / f"f{idx}.py").write_text(f"keyword item {idx}\n", encoding="utf-8")

    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_search_hits=3))
    server.handle_payload({"id": "req-limit-1", "method": "repo.refresh_index", "params": {}})

    blocked = server.handle_payload(
        {
            "id": "req-limit-2",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "top_k": 10},
        }
    )
    assert blocked["blocked"] is True
    assert blocked["error"]["code"] == "PATH_BLOCKED"

    allowed = server.handle_payload(
        {
            "id": "req-limit-3",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "top_k": 2},
        }
    )
    assert allowed["ok"] is True
    assert len(allowed["result"]["hits"]) == 2
