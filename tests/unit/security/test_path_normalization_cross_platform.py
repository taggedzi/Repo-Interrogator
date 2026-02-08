from __future__ import annotations

import json
from pathlib import Path

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
    payload = {
        "id": "req-block-1",
        "method": "repo.open_file",
        "params": {"path": "../secrets.txt", "start_line": 1, "end_line": 5},
    }

    response = server.handle_payload(json.loads(json.dumps(payload)))

    assert response["request_id"] == "req-block-1"
    assert response["blocked"] is True
    assert response["ok"] is False
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "Path traversal is blocked.",
    }
    assert response["result"] == {
        "reason": "Path traversal is blocked.",
        "hint": "Remove '..' segments and use a repository-relative path.",
    }
