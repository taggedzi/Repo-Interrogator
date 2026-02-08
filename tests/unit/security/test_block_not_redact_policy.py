from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_denylisted_open_file_is_blocked_without_content_leak(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("API_KEY=super-secret-value\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    response = server.handle_payload(
        {
            "id": "req-deny",
            "method": "repo.open_file",
            "params": {"path": ".env", "start_line": 1, "end_line": 1},
        }
    )

    assert response["blocked"] is True
    assert response["ok"] is False
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "File is denylisted by security policy.",
    }
    assert "numbered_lines" not in response["result"]
    assert "super-secret-value" not in str(response)
