"""Shared test helpers for MCP JSON-RPC 2.0 response assertions."""

from __future__ import annotations

import json
from typing import Any

from repo_mcp.server import StdioServer


def call_tool(
    server: StdioServer,
    request_id: str | int,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, Any]:
    """Send a tools/call request via handle_payload and return the full JSON-RPC 2.0 response."""
    return server.handle_payload(  # type: ignore[return-value]
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    )


def extract_result(response: dict[str, Any]) -> dict[str, Any]:
    """Parse and return the tool result dict from a successful tools/call response.

    Raises AssertionError if the response contains a protocol error or isError flag.
    """
    assert "error" not in response, f"Unexpected JSON-RPC error: {response}"
    result = response["result"]
    assert not result.get("isError"), f"Tool returned isError: {response}"
    text = result["content"][0]["text"]
    return json.loads(text)  # type: ignore[no-any-return]


def is_tool_error(response: dict[str, Any]) -> bool:
    """Return True if the tool returned an isError result (blocked path, policy, or tool error)."""
    result = response.get("result", {})
    return bool(result.get("isError", False))


def tool_error_text(response: dict[str, Any]) -> str:
    """Return the error message text from an isError tool response."""
    return str(response["result"]["content"][0]["text"])
