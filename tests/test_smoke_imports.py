from __future__ import annotations

from repo_mcp import server


def test_server_main_is_callable() -> None:
    assert callable(server.main)
