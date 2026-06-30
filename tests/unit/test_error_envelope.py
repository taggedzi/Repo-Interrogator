from __future__ import annotations

from tests.helpers import call_tool, is_tool_error, tool_error_text

from repo_mcp.server import create_server


def test_malformed_json_returns_parse_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_json_line("{not-json")

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] is None
    assert response["error"]["code"] == -32700
    assert "Parse error" in response["error"]["message"]


def test_unknown_method_returns_method_not_found() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": "abc-123", "jsonrpc": "2.0", "method": "repo.unknown", "params": {}}
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "abc-123"
    assert response["error"]["code"] == -32601
    assert "repo.unknown" in response["error"]["message"]


def test_unknown_tool_name_in_tools_call_returns_tool_error() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "abc-456", "repo.nonexistent", {})

    assert is_tool_error(response)
    assert "UNKNOWN_TOOL" in tool_error_text(response)


def test_invalid_tools_call_name_returns_protocol_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": 7,
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "", "arguments": {}},
        }
    )

    assert response is not None
    assert response["id"] == 7
    assert response["error"]["code"] == -32602
    assert "name" in response["error"]["message"]


def test_invalid_tools_call_arguments_returns_protocol_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": "bad-args",
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "repo.status", "arguments": []},
        }
    )

    assert response is not None
    assert response["id"] == "bad-args"
    assert response["error"]["code"] == -32602
    assert "arguments" in response["error"]["message"]
