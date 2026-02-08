from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server


def test_audit_log_writes_jsonl_schema(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-100", "method": "repo.status", "params": {}})

    audit_path = tmp_path / ".repo_mcp" / "audit.jsonl"
    assert audit_path.exists()

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    event = json.loads(lines[-1])

    assert set(event.keys()) == {
        "blocked",
        "error_code",
        "metadata",
        "ok",
        "request_id",
        "timestamp",
        "tool",
    }
    assert event["request_id"] == "req-100"
    assert event["tool"] == "repo.status"
    assert event["ok"] is True
    assert event["blocked"] is False
    assert event["error_code"] is None
    assert isinstance(event["timestamp"], str)
    assert isinstance(event["metadata"], dict)
