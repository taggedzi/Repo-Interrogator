from __future__ import annotations

import io
import json

from repo_mcp.server import create_server


def test_stdio_server_routes_multiple_requests() -> None:
    server = create_server(repo_root=".")
    in_stream = io.StringIO(
        "\n".join(
            [
                json.dumps({"id": "req-1", "method": "repo.status", "params": {}}),
                json.dumps(
                    {
                        "id": "req-2",
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

    assert first["request_id"] == "req-1"
    assert first["ok"] is True
    assert isinstance(first["result"], dict)

    assert second["request_id"] == "req-2"
    assert second["ok"] is True
    assert isinstance(second["result"], dict)
