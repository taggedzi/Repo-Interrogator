from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_open_file_path_normalization_windows_and_posix_inputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    windows = server.handle_payload(
        {
            "id": "req-plat-1",
            "method": "repo.open_file",
            "params": {"path": r"src\main.py", "start_line": 1, "end_line": 1},
        }
    )
    posix = server.handle_payload(
        {
            "id": "req-plat-2",
            "method": "repo.open_file",
            "params": {"path": "src/main.py", "start_line": 1, "end_line": 1},
        }
    )

    assert windows["ok"] is True
    assert posix["ok"] is True
    assert windows["result"]["numbered_lines"] == posix["result"]["numbered_lines"]


def test_search_path_prefix_normalization_backslash_vs_slash(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text("keyword alpha\n", encoding="utf-8")
    (tmp_path / "src" / "beta.py").write_text("keyword beta\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-plat-3", "method": "repo.refresh_index", "params": {}})

    slash = server.handle_payload(
        {
            "id": "req-plat-4",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "top_k": 10, "path_prefix": "src/"},
        }
    )
    backslash = server.handle_payload(
        {
            "id": "req-plat-5",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "top_k": 10, "path_prefix": r"src\\"},
        }
    )

    assert slash["ok"] is True
    assert backslash["ok"] is True
    assert slash["result"]["hits"] == backslash["result"]["hits"]
