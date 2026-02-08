from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_repo_audit_log_returns_recent_sanitized_entries(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    file_path = tmp_path / "app.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    server.handle_payload({"id": "req-300", "method": "repo.status", "params": {}})
    server.handle_payload(
        {
            "id": "req-301",
            "method": "repo.open_file",
            "params": {"path": "app.py", "start_line": 1, "end_line": 1},
        }
    )

    response = server.handle_payload(
        {
            "id": "req-302",
            "method": "repo.audit_log",
            "params": {"limit": 2},
        }
    )

    assert response["ok"] is True
    assert response["blocked"] is False
    result = response["result"]
    assert isinstance(result, dict)
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
    server.handle_payload({"id": "req-400", "method": "repo.status", "params": {}})
    response = server.handle_payload(
        {
            "id": "req-401",
            "method": "repo.audit_log",
            "params": {"since": "9999-01-01T00:00:00.000Z"},
        }
    )

    entries = response["result"]["entries"]
    assert entries == []
