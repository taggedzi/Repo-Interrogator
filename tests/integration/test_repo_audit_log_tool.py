from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_repo_audit_log_returns_recent_sanitized_entries(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    file_path = tmp_path / "app.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    call_tool(server, "req-300", "repo.status", {})
    call_tool(
        server, "req-301", "repo.open_file", {"path": "app.py", "start_line": 1, "end_line": 1}
    )

    result = extract_result(call_tool(server, "req-302", "repo.audit_log", {"limit": 2}))

    entries = result["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 2

    first = entries[0]
    second = entries[1]

    assert first["request_id"] == "req-300"
    assert first["tool"] == "repo.status"
    assert second["request_id"] == "req-301"
    assert second["tool"] == "repo.open_file"
    assert "print('hello')" not in str(entries)
    assert second["metadata"]["path"] == "app.py"


def test_repo_audit_log_since_filter(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-400", "repo.status", {})

    result = extract_result(
        call_tool(server, "req-401", "repo.audit_log", {"since": "9999-01-01T00:00:00.000Z"})
    )

    assert result["entries"] == []
