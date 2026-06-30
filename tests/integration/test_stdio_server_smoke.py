from __future__ import annotations

import io
import json

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_stdio_server_routes_multiple_requests() -> None:
    server = create_server(repo_root=".")
    in_stream = io.StringIO(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "req-1",
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": "repo.status", "arguments": {}},
                    }
                ),
                json.dumps(
                    {
                        "id": "req-2",
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": "repo.search", "arguments": {"query": "x"}},
                    }
                ),
            ]
        )
        + "\n"
    )
    out_stream = io.StringIO()

    server.serve(in_stream=in_stream, out_stream=out_stream)
    lines = [line for line in out_stream.getvalue().splitlines() if line]

    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["id"] == "req-1"
    assert first["jsonrpc"] == "2.0"
    assert "result" in first

    assert second["id"] == "req-2"
    assert second["jsonrpc"] == "2.0"
    assert "result" in second


def test_handle_payload_status_via_tools_call() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "smoke-1", "repo.status", {})

    result = extract_result(response)
    assert "index_status" in result
    assert "limits_summary" in result
