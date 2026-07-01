from __future__ import annotations

import io
import json

from tests.helpers import call_tool

from repo_mcp.server import create_server

EXPECTED_TOOLS = [
    "repo.status",
    "repo.list_files",
    "repo.open_file",
    "repo.outline",
    "repo.search",
    "repo.build_context_bundle",
    "repo.references",
    "repo.find_definition",
    "repo.refresh_index",
    "repo.audit_log",
]


def test_initialize_returns_mcp_capabilities() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.0.1"},
            },
        }
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "repo-interrogator"
    assert isinstance(result["serverInfo"]["version"], str)


def test_tools_list_returns_all_nine_tools() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": 2, "jsonrpc": "2.0", "method": "tools/list", "params": {}}
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    tools = response["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == set(EXPECTED_TOOLS)
    for tool in tools:
        assert isinstance(tool["description"], str)
        assert tool["description"]
        assert tool["inputSchema"]["type"] == "object"


def test_notification_produces_no_response() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )

    assert response is None


def test_tools_call_status_returns_content_block() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "tc-1", "repo.status", {})

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "tc-1"
    result = response["result"]
    assert not result.get("isError")
    content = result["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    data = json.loads(content[0]["text"])
    assert "index_status" in data


def test_full_mcp_handshake_and_tool_call() -> None:
    server = create_server(repo_root=".")
    in_lines = [
        json.dumps(
            {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "0"},
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
        json.dumps({"id": 2, "jsonrpc": "2.0", "method": "tools/list", "params": {}}),
        json.dumps(
            {
                "id": 3,
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "repo.status", "arguments": {}},
            }
        ),
    ]
    in_stream = io.StringIO("\n".join(in_lines) + "\n")
    out_stream = io.StringIO()

    server.serve(in_stream=in_stream, out_stream=out_stream)

    lines = [line for line in out_stream.getvalue().splitlines() if line]
    assert len(lines) == 3  # notification produces no response
    init_resp = json.loads(lines[0])
    list_resp = json.loads(lines[1])
    call_resp = json.loads(lines[2])
    assert init_resp["id"] == 1
    assert init_resp["result"]["protocolVersion"] == "2024-11-05"
    assert list_resp["id"] == 2
    assert len(list_resp["result"]["tools"]) == 10
    assert call_resp["id"] == 3
    assert not call_resp["result"].get("isError")


def test_unknown_method_returns_32601() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": "x", "jsonrpc": "2.0", "method": "rpc.discover", "params": {}}
    )

    assert response is not None
    assert response["error"]["code"] == -32601


def test_parse_error_returns_32700() -> None:
    server = create_server(repo_root=".")

    response = server.handle_json_line("{bad json")

    assert response is not None
    assert response["error"]["code"] == -32700
    assert response["id"] is None
