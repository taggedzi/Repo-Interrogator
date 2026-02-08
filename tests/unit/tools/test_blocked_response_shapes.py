from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_blocked_open_file_response_shape_has_no_content_fields(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    response = server.handle_payload(
        {
            "id": "req-block-shape-1",
            "method": "repo.open_file",
            "params": {"path": "../secret.txt", "start_line": 1, "end_line": 3},
        }
    )

    assert response["ok"] is False
    assert response["blocked"] is True
    assert response["error"]["code"] == "PATH_BLOCKED"
    assert set(response["result"].keys()) == {"reason", "hint"}
    assert "numbered_lines" not in response["result"]


def test_blocked_outline_response_shape_has_no_symbols(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    response = server.handle_payload(
        {
            "id": "req-block-shape-2",
            "method": "repo.outline",
            "params": {"path": "../outside.py"},
        }
    )

    assert response["ok"] is False
    assert response["blocked"] is True
    assert response["error"]["code"] == "PATH_BLOCKED"
    assert set(response["result"].keys()) == {"reason", "hint"}
    assert "symbols" not in response["result"]
