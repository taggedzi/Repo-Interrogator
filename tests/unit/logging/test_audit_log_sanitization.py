from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server


def test_audit_log_sanitizes_query_and_prompt_values(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload(
        {
            "id": "req-200",
            "method": "repo.search",
            "params": {"query": "API_KEY=top-secret", "top_k": 1},
        }
    )

    audit_path = tmp_path / ".repo_mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    event = entries[-1]

    metadata = event["metadata"]
    assert metadata["query_present"] is True
    assert metadata["query_length"] == len("API_KEY=top-secret")
    assert "query" not in metadata
    assert "API_KEY=top-secret" not in json.dumps(event, sort_keys=True)


def test_audit_log_sanitizes_unknown_string_values(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload(
        {
            "id": "req-201",
            "method": "repo.search",
            "params": {"query": "x", "custom_note": "token=abc123"},
        }
    )

    audit_path = tmp_path / ".repo_mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    metadata = entries[-1]["metadata"]

    assert metadata["custom_note_present"] is True
    assert metadata["custom_note_length"] == len("token=abc123")
    assert "custom_note" not in metadata
