from __future__ import annotations

from repo_mcp.tools import ToolRegistry


def test_registry_keeps_deterministic_registration_order() -> None:
    registry = ToolRegistry()
    registry.register("repo.alpha", lambda _: {"tool": "alpha"})
    registry.register("repo.beta", lambda _: {"tool": "beta"})

    assert registry.names() == ("repo.alpha", "repo.beta")


def test_registry_dispatches_registered_tool() -> None:
    registry = ToolRegistry()
    registry.register("repo.echo", lambda payload: {"payload": payload})

    result = registry.dispatch("repo.echo", {"k": "v"})

    assert result == {"payload": {"k": "v"}}
