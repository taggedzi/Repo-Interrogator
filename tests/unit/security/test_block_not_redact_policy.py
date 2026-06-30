from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error

from repo_mcp.server import create_server


def test_denylisted_open_file_is_blocked_without_content_leak(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("API_KEY=super-secret-value\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(
        server, "req-deny", "repo.open_file", {"path": ".env", "start_line": 1, "end_line": 1}
    )

    assert is_tool_error(response)
    assert "super-secret-value" not in str(response)
    assert "numbered_lines" not in str(response)
