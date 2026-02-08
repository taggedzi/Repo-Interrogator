from __future__ import annotations

import json

from repo_mcp.server import create_server


def test_malformed_json_returns_invalid_json_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_json_line("{not-json")

    assert response["ok"] is False
    assert response["error"] == {
        "code": "INVALID_JSON",
        "message": "Request must be valid JSON.",
    }
    assert str(response["request_id"]).startswith("req-")


def test_unknown_tool_returns_explicit_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": "abc-123", "method": "repo.unknown", "params": {"k": "v"}}
    )

    assert response["ok"] is False
    assert response["request_id"] == "abc-123"
    assert response["error"] == {
        "code": "UNKNOWN_TOOL",
        "message": "Unknown tool: repo.unknown",
    }


def test_invalid_tools_call_params_returns_invalid_params_error() -> None:
    server = create_server(repo_root=".")
    payload = {"id": 7, "method": "tools/call", "params": {"name": "repo.status", "arguments": []}}

    response = server.handle_payload(json.loads(json.dumps(payload)))

    assert response["ok"] is False
    assert response["request_id"] == "7"
    assert response["error"] == {
        "code": "INVALID_PARAMS",
        "message": "tools/call params.arguments must be an object.",
    }
