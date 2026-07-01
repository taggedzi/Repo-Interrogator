from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server
from repo_mcp.tools.schemas import TOOL_SCHEMAS

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


def test_all_nine_tools_are_present() -> None:
    assert set(TOOL_SCHEMAS.keys()) == set(EXPECTED_TOOLS)


def test_each_schema_has_required_mcp_fields() -> None:
    for name, schema in TOOL_SCHEMAS.items():
        assert schema["name"] == name, f"{name}: name field mismatch"
        assert isinstance(schema["description"], str), f"{name}: description must be str"
        assert schema["description"], f"{name}: description must be non-empty"
        input_schema = schema["inputSchema"]
        assert isinstance(input_schema, dict), f"{name}: inputSchema must be dict"
        assert input_schema.get("type") == "object", f"{name}: inputSchema type must be 'object'"
        assert "properties" in input_schema, f"{name}: inputSchema must have properties"


def test_required_params_are_correct() -> None:
    assert TOOL_SCHEMAS["repo.open_file"]["inputSchema"]["required"] == ["path"]
    assert TOOL_SCHEMAS["repo.outline"]["inputSchema"]["required"] == ["path"]
    assert TOOL_SCHEMAS["repo.search"]["inputSchema"]["required"] == ["query"]
    assert TOOL_SCHEMAS["repo.references"]["inputSchema"]["required"] == ["symbol"]
    assert TOOL_SCHEMAS["repo.build_context_bundle"]["inputSchema"]["required"] == [
        "prompt",
        "budget",
    ]


def test_builtin_tools_all_have_metadata_registered(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    tools = server._registry.list_tools()
    names = {t["name"] for t in tools}
    assert names == set(EXPECTED_TOOLS)
    for tool in tools:
        assert tool["description"]
        assert tool["inputSchema"]
