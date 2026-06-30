from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server
from tests.helpers import call_tool, extract_result, is_tool_error


def test_open_file_path_normalization_windows_and_posix_inputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    windows = call_tool(
        server,
        "req-plat-1",
        "repo.open_file",
        {"path": r"src\main.py", "start_line": 1, "end_line": 1},
    )
    posix = call_tool(
        server,
        "req-plat-2",
        "repo.open_file",
        {"path": "src/main.py", "start_line": 1, "end_line": 1},
    )

    assert not is_tool_error(windows)
    assert not is_tool_error(posix)
    assert extract_result(windows)["numbered_lines"] == extract_result(posix)["numbered_lines"]


def test_search_path_prefix_normalization_backslash_vs_slash(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text("keyword alpha\n", encoding="utf-8")
    (tmp_path / "src" / "beta.py").write_text("keyword beta\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-plat-3", "repo.refresh_index", {})

    slash = call_tool(
        server,
        "req-plat-4",
        "repo.search",
        {"query": "keyword", "mode": "bm25", "top_k": 10, "path_prefix": "src/"},
    )
    backslash = call_tool(
        server,
        "req-plat-5",
        "repo.search",
        {"query": "keyword", "mode": "bm25", "top_k": 10, "path_prefix": r"src\\"},
    )

    assert not is_tool_error(slash)
    assert not is_tool_error(backslash)
    assert extract_result(slash)["hits"] == extract_result(backslash)["hits"]
