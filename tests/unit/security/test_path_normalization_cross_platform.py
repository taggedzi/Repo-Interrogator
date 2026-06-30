from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error, tool_error_text

from repo_mcp.security import resolve_repo_path
from repo_mcp.server import create_server


def test_windows_separator_path_normalizes_to_same_file(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "main.py"
    py_file.write_text("print('ok')\n", encoding="utf-8")

    resolved = resolve_repo_path(repo_root=tmp_path, candidate=r"src\main.py")

    assert resolved == py_file.resolve()


def test_blocked_open_file_response_does_not_include_file_content() -> None:
    server = create_server(repo_root=".")

    response = call_tool(
        server,
        "req-block-1",
        "repo.open_file",
        {"path": "../secrets.txt", "start_line": 1, "end_line": 5},
    )

    assert response["id"] == "req-block-1"
    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "Path traversal" in text
