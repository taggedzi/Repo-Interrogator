from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import call_tool

from repo_mcp.server import create_server


def test_bundle_audit_log_sanitizes_prompt_and_budget(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 'a'\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-san-1", "repo.refresh_index", {})
    call_tool(
        server,
        "req-san-2",
        "repo.build_context_bundle",
        {
            "prompt": "API_KEY=super-secret-token",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    audit_path = tmp_path / ".repo_mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    bundle_entries = [e for e in entries if e.get("tool") == "repo.build_context_bundle"]
    assert bundle_entries
    event = bundle_entries[-1]
    metadata = event["metadata"]

    assert metadata["prompt_present"] is True
    assert metadata["prompt_length"] == len("API_KEY=super-secret-token")
    assert "prompt" not in metadata
    assert metadata["budget_type"] == "dict"
    assert metadata["budget_keys"] == ["max_files", "max_total_lines"]
    rendered = json.dumps(event, sort_keys=True)
    assert "super-secret-token" not in rendered
    assert "excerpt" not in rendered
