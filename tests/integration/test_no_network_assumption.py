from __future__ import annotations

import socket
from pathlib import Path

from repo_mcp.server import create_server


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
    assert server.handle_payload({"id": "req-net-1", "method": "repo.status", "params": {}})["ok"]
    assert server.handle_payload({"id": "req-net-2", "method": "repo.refresh_index", "params": {}})[
        "ok"
    ]
    assert server.handle_payload(
        {
            "id": "req-net-3",
            "method": "repo.search",
            "params": {"query": "parse", "mode": "bm25", "top_k": 5},
        }
    )["ok"]
    assert server.handle_payload(
        {"id": "req-net-4", "method": "repo.outline", "params": {"path": "src/x.py"}}
    )["ok"]
    assert server.handle_payload(
        {
            "id": "req-net-5",
            "method": "repo.references",
            "params": {"symbol": "parse"},
        }
    )["ok"]
    assert server.handle_payload(
        {
            "id": "req-net-6",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "parse x",
                "budget": {"max_files": 1, "max_total_lines": 10},
                "strategy": "hybrid",
                "include_tests": True,
            },
        }
    )["ok"]
    assert server.handle_payload({"id": "req-net-7", "method": "repo.audit_log", "params": {}})[
        "ok"
    ]
