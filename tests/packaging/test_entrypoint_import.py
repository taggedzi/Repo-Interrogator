from __future__ import annotations

from repo_mcp.server import main


def test_server_entrypoint_importable() -> None:
    assert callable(main)
