from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_path_traversal_open_file_returns_is_error(tmp_path: Path) -> None:
    from repo_mcp.server import create_server

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(
        server,
        "block-1",
        "repo.open_file",
        {"path": "../secret.txt", "start_line": 1, "end_line": 3},
    )

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "numbered_lines" not in text


def test_path_traversal_outline_returns_is_error(tmp_path: Path) -> None:
    from repo_mcp.server import create_server

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(server, "block-2", "repo.outline", {"path": "../outside.py"})

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "symbols" not in text
