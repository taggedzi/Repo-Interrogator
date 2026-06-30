from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_cross_platform_style_inputs_produce_stable_outputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        "class A:\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "\n"
        "def parse_token(text: str) -> str:\n"
        "    return text\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-cross-1", "repo.refresh_index", {})

    open_posix = call_tool(
        server,
        "req-cross-2",
        "repo.open_file",
        {"path": "src/mod.py", "start_line": 1, "end_line": 5},
    )
    open_windows = call_tool(
        server,
        "req-cross-3",
        "repo.open_file",
        {"path": r"src\mod.py", "start_line": 1, "end_line": 5},
    )

    outline_posix = call_tool(server, "req-cross-4", "repo.outline", {"path": "src/mod.py"})
    outline_windows = call_tool(server, "req-cross-5", "repo.outline", {"path": r"src\mod.py"})

    search_slash = call_tool(
        server,
        "req-cross-6",
        "repo.search",
        {"query": "parse token", "mode": "bm25", "top_k": 10, "path_prefix": "src/"},
    )
    search_backslash = call_tool(
        server,
        "req-cross-7",
        "repo.search",
        {"query": "parse token", "mode": "bm25", "top_k": 10, "path_prefix": r"src\\"},
    )

    assert not is_tool_error(open_posix)
    assert not is_tool_error(open_windows)
    assert (
        extract_result(open_posix)["numbered_lines"]
        == extract_result(open_windows)["numbered_lines"]
    )

    assert not is_tool_error(outline_posix)
    assert not is_tool_error(outline_windows)
    assert extract_result(outline_posix) == extract_result(outline_windows)

    assert not is_tool_error(search_slash)
    assert not is_tool_error(search_backslash)
    assert extract_result(search_slash)["hits"] == extract_result(search_backslash)["hits"]
