from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_list_files_ordering_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "z.py").write_text("print('z')\n", encoding="utf-8")
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "src" / "m.py").write_text("print('m')\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    first = server.handle_payload(
        {"id": "req-order-1", "method": "repo.list_files", "params": {"max_results": 10}}
    )
    second = server.handle_payload(
        {"id": "req-order-2", "method": "repo.list_files", "params": {"max_results": 10}}
    )

    first_paths = [item["path"] for item in first["result"]["files"]]
    second_paths = [item["path"] for item in second["result"]["files"]]
    assert first_paths == second_paths == ["src/a.py", "src/m.py", "src/z.py"]


def test_search_ordering_is_deterministic_for_repeated_calls(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("token token\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_text("token token\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-order-3", "method": "repo.refresh_index", "params": {}})

    first = server.handle_payload(
        {
            "id": "req-order-4",
            "method": "repo.search",
            "params": {"query": "token", "mode": "bm25", "top_k": 10},
        }
    )
    second = server.handle_payload(
        {
            "id": "req-order-5",
            "method": "repo.search",
            "params": {"query": "token", "mode": "bm25", "top_k": 10},
        }
    )

    first_hits = [(hit["path"], hit["start_line"]) for hit in first["result"]["hits"]]
    second_hits = [(hit["path"], hit["start_line"]) for hit in second["result"]["hits"]]
    assert first_hits == second_hits
    assert first_hits == [("pkg/a.py", 1), ("pkg/b.py", 1)]
