from __future__ import annotations

import socket
from pathlib import Path

from repo_mcp.server import create_server
from tests.helpers import call_tool, is_tool_error


def test_no_network_calls_during_tool_workflow(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text(
        "def parse(x: str) -> str:\n    return x\n",
        encoding="utf-8",
    )

    def _blocked_create_connection(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            f"Network call attempted: create_connection args={args} kwargs={kwargs}"
        )

    base_socket = socket.socket

    class _BlockedSocket(base_socket):
        def connect(self, address):  # type: ignore[no-untyped-def]
            raise AssertionError(f"Network call attempted: connect address={address}")

    monkeypatch.setattr(socket, "create_connection", _blocked_create_connection)
    monkeypatch.setattr(socket, "socket", _BlockedSocket)

    server = create_server(repo_root=str(tmp_path))
    assert not is_tool_error(call_tool(server, "req-net-1", "repo.status", {}))
    assert not is_tool_error(call_tool(server, "req-net-2", "repo.refresh_index", {}))
    assert not is_tool_error(
        call_tool(
            server,
            "req-net-3",
            "repo.search",
            {"query": "parse", "mode": "bm25", "top_k": 5},
        )
    )
    assert not is_tool_error(call_tool(server, "req-net-4", "repo.outline", {"path": "src/x.py"}))
    assert not is_tool_error(
        call_tool(
            server,
            "req-net-5",
            "repo.references",
            {"symbol": "parse"},
        )
    )
    assert not is_tool_error(
        call_tool(
            server,
            "req-net-6",
            "repo.build_context_bundle",
            {
                "prompt": "parse x",
                "budget": {"max_files": 1, "max_total_lines": 10},
                "strategy": "hybrid",
                "include_tests": True,
            },
        )
    )
    assert not is_tool_error(call_tool(server, "req-net-7", "repo.audit_log", {}))
