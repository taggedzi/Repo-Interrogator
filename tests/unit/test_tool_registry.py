from __future__ import annotations

from repo_mcp.tools import ToolRegistry
from repo_mcp.tools.registry import ToolMetadata


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


def test_list_tools_returns_empty_when_no_metadata_registered() -> None:
    registry = ToolRegistry()
    registry.register("repo.no_meta", lambda _: {})

    assert registry.list_tools() == []


def test_list_tools_returns_definition_for_tools_with_metadata() -> None:
    registry = ToolRegistry()
    meta = ToolMetadata(
        name="repo.search",
        description="Search the repo.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    registry.register("repo.search", lambda _: {}, metadata=meta)

    tools = registry.list_tools()

    assert len(tools) == 1
    assert tools[0]["name"] == "repo.search"
    assert tools[0]["description"] == "Search the repo."
    assert tools[0]["inputSchema"] == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }


def test_list_tools_preserves_registration_order() -> None:
    registry = ToolRegistry()
    for name in ["repo.status", "repo.search", "repo.outline"]:
        registry.register(
            name,
            lambda _: {},
            metadata=ToolMetadata(
                name=name,
                description=f"Desc {name}",
                input_schema={"type": "object", "properties": {}},
            ),
        )

    names = [t["name"] for t in registry.list_tools()]
    assert names == ["repo.status", "repo.search", "repo.outline"]
