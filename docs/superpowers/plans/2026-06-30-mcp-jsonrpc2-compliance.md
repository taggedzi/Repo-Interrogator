# MCP JSON-RPC 2.0 Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom `{ok, result, blocked, warnings, request_id}` envelope with full MCP/JSON-RPC 2.0 compliance so standard MCP clients (Claude Desktop, Claude Code, Cursor) can connect and use all 9 tools without any custom configuration.

**Architecture:** The transport/dispatch layer in `server.py` is replaced with JSON-RPC 2.0 framing, `initialize` negotiation, `tools/list` discovery, and `tools/call` content-block responses. Tool handlers in `builtin.py` are untouched. A new `schemas.py` holds JSON Schema for all 9 tools, consumed by an updated `ToolRegistry` to serve `tools/list`. A shared test helper module (`tests/helpers.py`) abstracts the new response format so the 20 test files that checked the old envelope can be updated systematically.

**Tech Stack:** Python 3.11+, stdlib only (`json`, `importlib.metadata`), pytest, ruff, mypy

## Global Constraints

- No new runtime dependencies — stdlib only
- No LLM calls; all logic deterministic
- All commands run inside `.venv/` — activate first: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
- Run `python -m ruff format .`, `python -m ruff check .`, `python -m mypy src`, `python -m pytest -q` after every task — fix all failures before moving on
- ADR required for transport/schema changes per `CLAUDE.md`
- No backward compatibility with the old custom envelope — drop it entirely
- `SPEC.md > docs/ > code` authority hierarchy

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `docs/adr/ADR-0017-mcp-jsonrpc2-compliance.md` | Documents the protocol switch decision |
| Create | `src/repo_mcp/tools/schemas.py` | JSON Schema definitions for all 9 tools |
| Modify | `src/repo_mcp/tools/registry.py` | Add `ToolMetadata`, `list_tools()` to `ToolRegistry` |
| Modify | `src/repo_mcp/tools/builtin.py` | Pass `ToolMetadata` to every `registry.register` call |
| Modify | `src/repo_mcp/server.py` | Replace custom envelope with JSON-RPC 2.0 protocol |
| Create | `tests/helpers.py` | Shared test helpers for new response format |
| Modify | `tests/unit/test_error_envelope.py` | Test JSON-RPC 2.0 errors |
| Create | `tests/integration/test_mcp_protocol.py` | Full MCP handshake + discovery tests |
| Modify | `tests/unit/tools/test_blocked_response_shapes.py` | Test `isError` blocked responses |
| Modify | `tests/integration/test_stdio_server_smoke.py` | Test MCP routing |
| Modify | `tests/integration/test_tool_contract_matrix.py` | Test all 9 tools via `tools/call` |
| Modify | `tests/integration/test_stdio_workflow_e2e.py` | E2E test with MCP helpers |
| Modify | `tests/unit/security/test_limit_enforcement.py` | Update 4 assertions |
| Modify | `tests/unit/security/test_block_not_redact_policy.py` | Update 1 assertion |
| Modify | `tests/unit/security/test_path_normalization_cross_platform.py` | Update 1 assertion |
| Modify | `tests/unit/search/test_bm25_basic.py` | Update 2 assertions |
| Modify | `tests/unit/index/test_force_refresh_behavior.py` | Update 3 assertions |
| Modify | `tests/unit/index/test_index_schema_versioning.py` | Update 2 assertions |
| Modify | `tests/unit/logging/test_bundle_audit_sanitization.py` | Update 1 assertion |
| Modify | `tests/unit/bundler/test_bundle_export_policy.py` | Update 3 assertions |
| Modify | `tests/integration/test_repo_status_config_snapshot.py` | Update 2 assertions |
| Modify | `tests/integration/test_repo_search_tool.py` | Update 3 assertions |
| Modify | `tests/integration/test_repo_audit_log_tool.py` | Update 5 assertions |
| Modify | `tests/integration/test_repo_outline_tool.py` | Update 3 assertions |
| Modify | `tests/integration/test_repo_outline_multilanguage_selection.py` | Update loop assertions |
| Modify | `tests/integration/test_repo_references_tool.py` | Update 6 assertions |
| Modify | `tests/integration/test_repo_references_adapter_grouping.py` | Update 2 assertions |
| Modify | `tests/integration/test_bundle_with_non_python_outline.py` | Update 3 assertions |
| Modify | `tests/integration/test_repo_build_context_bundle_tool.py` | Update 6 assertions |
| Modify | `docs/AI_INTEGRATION.md` | Correct client config and protocol docs |

> **Not updated:** `tests/unit/bundler/test_quality_golden_prompts.py` — uses old method names as hardcoded mock data only; does not call `handle_payload` or check envelope fields.

---

## Task 1: ADR-0017

**Files:**
- Create: `docs/adr/ADR-0017-mcp-jsonrpc2-compliance.md`

**Interfaces:**
- Consumes: nothing
- Produces: nothing (docs only)

- [ ] **Step 1: Create the ADR**

```markdown
## ADR-0017 - MCP JSON-RPC 2.0 Protocol Compliance

**Status:** Accepted
**Date:** 2026-06-30

### Context

The server used a proprietary `{ok, result, blocked, warnings, request_id}` envelope. Standard MCP clients (Claude Desktop, Claude Code, Cursor) open a connection by sending `initialize`, then `notifications/initialized`, then `tools/list` — all using JSON-RPC 2.0 framing. The custom envelope caused the `initialize` request to return `UNKNOWN_TOOL`, which killed the connection before tool discovery could occur.

The project's stated goal is to make AI-assisted code understanding easy. Without MCP compliance, no standard AI client can use the server. The server has had zero external downloads; there is no backward-compatibility obligation.

### Decision

Replace the custom envelope with full MCP-compliant JSON-RPC 2.0:

- JSON-RPC 2.0 responses: `{"jsonrpc":"2.0","id":...,"result":{...}}` for success, `{"jsonrpc":"2.0","id":...,"error":{"code":...,"message":"..."}}` for protocol-level errors
- `initialize` handler — returns `protocolVersion`, `capabilities`, `serverInfo`
- Notifications (requests without `id`, e.g. `notifications/initialized`) — silently ignored, no response
- `tools/list` — returns all 9 tool definitions with `name`, `description`, `inputSchema`
- `tools/call` — results wrapped as `{"content":[{"type":"text","text":"...json..."}]}`
- Tool errors (path blocks, policy violations, dispatch errors) — returned as `{"content":[...],"isError":true}` so the AI client sees a human-readable message
- Protocol-level errors (parse errors, unknown methods) — returned as JSON-RPC error objects

The old direct-method protocol (`{"method":"repo.status","params":{}}`) is removed entirely.

### Rationale

- JSON-RPC 2.0 is the MCP wire standard; compliance gives immediate compatibility with all MCP clients
- `tools/list` enables zero-configuration tool discovery — no manual preconfiguration of tool names
- `isError` for tool failures keeps the AI informed; JSON-RPC errors for protocol failures keeps the framing clean
- No backward-compat needed: sole developer, zero external users

### Consequences

- All standard MCP clients work immediately without custom configuration
- 20 test files that checked old envelope fields are updated using a shared `tests/helpers.py` module
- `AI_INTEGRATION.md` updated with correct MCP client setup instructions
- `StdioServer` loses `parse_request`, `extract_request_id`, `next_request_id`, `success_response`, `error_response`, `blocked_response`, `enforce_response_size_limit`, `log_request` — replaced by `jsonrpc_result`, `jsonrpc_error`, `tool_content`, `tool_error_content`, `_handle_initialize`, `_handle_tools_call`, `_log_request`
```

- [ ] **Step 2: Verify all required tools pass**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

Expected: all pass (docs-only change).

- [ ] **Step 3: Commit**

```bash
git add docs/adr/ADR-0017-mcp-jsonrpc2-compliance.md
git commit -m "docs: add ADR-0017 for MCP JSON-RPC 2.0 protocol compliance"
```

---

## Task 2: Tool Schemas Module

**Files:**
- Create: `src/repo_mcp/tools/schemas.py`
- Create: `tests/unit/tools/test_tool_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces: `TOOL_SCHEMAS: dict[str, dict[str, object]]` — keyed by tool name; each value has `"name"`, `"description"`, `"inputSchema"` keys

- [ ] **Step 1: Write the failing test**

Create `tests/unit/tools/test_tool_schemas.py`:

```python
from __future__ import annotations

from repo_mcp.tools.schemas import TOOL_SCHEMAS

EXPECTED_TOOLS = [
    "repo.status",
    "repo.list_files",
    "repo.open_file",
    "repo.outline",
    "repo.search",
    "repo.build_context_bundle",
    "repo.references",
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
    assert TOOL_SCHEMAS["repo.build_context_bundle"]["inputSchema"]["required"] == ["prompt", "budget"]
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/unit/tools/test_tool_schemas.py -q
```

Expected: `ModuleNotFoundError: No module named 'repo_mcp.tools.schemas'`

- [ ] **Step 3: Create `src/repo_mcp/tools/schemas.py`**

```python
"""JSON Schema definitions for all built-in MCP tools."""

from __future__ import annotations

TOOL_SCHEMAS: dict[str, dict[str, object]] = {
    "repo.status": {
        "name": "repo.status",
        "description": (
            "Return index state, active limits, enabled adapters, and effective config. "
            "Call this first to verify the server is connected and the index is ready."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "repo.list_files": {
        "name": "repo.list_files",
        "description": (
            "List readable source files under the repository root. "
            "Supports glob filtering. Use to discover what files exist before searching or opening."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "glob": {
                    "type": "string",
                    "description": "Glob pattern to filter results (e.g. 'src/**/*.py').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of files to return.",
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories (default false).",
                },
            },
        },
    },
    "repo.open_file": {
        "name": "repo.open_file",
        "description": (
            "Read a line range from a source file. Returns numbered lines. "
            "Specify start_line and end_line to read a focused range rather than the entire file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path (e.g. 'src/server.py').",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read, 1-indexed (default 1).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read, inclusive.",
                },
            },
            "required": ["path"],
        },
    },
    "repo.outline": {
        "name": "repo.outline",
        "description": (
            "Return the declaration structure of a file using AST (Python) or lexical analysis. "
            "Shows classes, functions, and other symbols with line ranges and parent context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path.",
                },
            },
            "required": ["path"],
        },
    },
    "repo.search": {
        "name": "repo.search",
        "description": (
            "Run BM25 full-text search over indexed repository chunks. "
            "Returns ranked hits with file path, line range, snippet, and matched terms. "
            "Run repo.refresh_index first if the index is not yet built."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms (BM25 keyword matching).",
                },
                "mode": {
                    "type": "string",
                    "enum": ["bm25"],
                    "description": "Search mode — only 'bm25' is supported in v1.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                },
                "file_glob": {
                    "type": "string",
                    "description": "Glob pattern to restrict search to matching files (e.g. 'src/**/*.py').",
                },
                "path_prefix": {
                    "type": "string",
                    "description": "Path prefix to restrict search scope (e.g. 'src/repo_mcp/').",
                },
            },
            "required": ["query"],
        },
    },
    "repo.build_context_bundle": {
        "name": "repo.build_context_bundle",
        "description": (
            "Build a compact, ranked, cited context bundle for a coding task. "
            "Combines search, outline, and cross-file references into a budget-bounded excerpt set. "
            "Each selection includes why_selected explaining which signals drove it. "
            "Requires the index to be built first (repo.refresh_index)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Natural language description of your coding task.",
                },
                "budget": {
                    "type": "object",
                    "description": "Size constraints for the bundle.",
                    "properties": {
                        "max_files": {
                            "type": "integer",
                            "description": "Maximum number of files to include.",
                        },
                        "max_total_lines": {
                            "type": "integer",
                            "description": "Maximum total lines across all selected excerpts.",
                        },
                    },
                    "required": ["max_files", "max_total_lines"],
                },
                "strategy": {
                    "type": "string",
                    "enum": ["hybrid"],
                    "description": "Bundle strategy — only 'hybrid' is supported in v1.",
                },
                "include_tests": {
                    "type": "boolean",
                    "description": "Whether to include test files in the bundle.",
                },
            },
            "required": ["prompt", "budget"],
        },
    },
    "repo.references": {
        "name": "repo.references",
        "description": (
            "Find all cross-file references to a named symbol using AST (Python) or lexical analysis. "
            "Returns file paths, line numbers, strategy, and confidence level per reference."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find references for (e.g. 'MyClass.my_method').",
                },
                "path": {
                    "type": "string",
                    "description": "Optional file path to scope the reference search to one file.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of references to return.",
                },
            },
            "required": ["symbol"],
        },
    },
    "repo.refresh_index": {
        "name": "repo.refresh_index",
        "description": (
            "Build or incrementally refresh the BM25 search index. "
            "Run this before searching or bundling if the index is stale or not yet built. "
            "Use force=true to rebuild from scratch."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force a full rebuild even if the index appears current.",
                },
            },
        },
    },
    "repo.audit_log": {
        "name": "repo.audit_log",
        "description": (
            "Read sanitized audit log entries for all tool calls made in this session. "
            "Useful for diagnostics and verifying what was called and whether it succeeded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "ISO timestamp — return only events after this time.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return.",
                },
            },
        },
    },
}
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/unit/tools/test_tool_schemas.py -q
```

Expected: `3 passed`

- [ ] **Step 5: Lint and type-check**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/repo_mcp/tools/schemas.py tests/unit/tools/test_tool_schemas.py
git commit -m "feat: add MCP tool schema definitions for tools/list discovery"
```

---

## Task 3: ToolRegistry Metadata Support

**Files:**
- Modify: `src/repo_mcp/tools/registry.py`
- Modify: `tests/unit/test_tool_registry.py`

**Interfaces:**
- Consumes: nothing new
- Produces:
  - `ToolMetadata(name: str, description: str, input_schema: dict[str, object])` — frozen dataclass
  - `ToolRegistry.register(name, handler, metadata=None)` — updated signature
  - `ToolRegistry.list_tools() -> list[dict[str, object]]` — returns MCP tool definition dicts

- [ ] **Step 1: Write the failing tests**

Replace `tests/unit/test_tool_registry.py` with:

```python
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
    assert tools[0]["inputSchema"] == {"type": "object", "properties": {"query": {"type": "string"}}}


def test_list_tools_preserves_registration_order() -> None:
    registry = ToolRegistry()
    for name in ["repo.status", "repo.search", "repo.outline"]:
        registry.register(
            name,
            lambda _: {},
            metadata=ToolMetadata(name=name, description=f"Desc {name}", input_schema={"type": "object", "properties": {}}),
        )

    names = [t["name"] for t in registry.list_tools()]
    assert names == ["repo.status", "repo.search", "repo.outline"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/unit/test_tool_registry.py -q
```

Expected: failures for tests importing `ToolMetadata` and calling `list_tools`.

- [ ] **Step 3: Update `src/repo_mcp/tools/registry.py`**

```python
"""Deterministic tool registration primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

ToolHandler = Callable[[dict[str, object]], dict[str, object]]


@dataclass(slots=True, frozen=True)
class ToolDispatchError(Exception):
    """Represents deterministic tool dispatch failures."""

    code: str
    message: str


@dataclass(slots=True, frozen=True)
class ToolMetadata:
    """MCP tool definition metadata: name, description, and JSON Schema."""

    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(slots=True)
class ToolRegistry:
    """In-memory tool registry preserving deterministic insertion order."""

    _handlers: dict[str, ToolHandler] = field(default_factory=dict)
    _metadata: dict[str, ToolMetadata] = field(default_factory=dict)

    def register(
        self,
        name: str,
        handler: ToolHandler,
        metadata: ToolMetadata | None = None,
    ) -> None:
        """Register a named handler with optional MCP metadata."""
        self._handlers[name] = handler
        if metadata is not None:
            self._metadata[name] = metadata

    def get(self, name: str) -> ToolHandler | None:
        """Return a handler by name."""
        return self._handlers.get(name)

    def names(self) -> tuple[str, ...]:
        """Return registered tool names in deterministic order."""
        return tuple(self._handlers.keys())

    def list_tools(self) -> list[dict[str, object]]:
        """Return MCP tool definitions for all tools that have metadata registered."""
        result: list[dict[str, object]] = []
        for name in self._handlers:
            meta = self._metadata.get(name)
            if meta is not None:
                result.append(
                    {
                        "description": meta.description,
                        "inputSchema": meta.input_schema,
                        "name": meta.name,
                    }
                )
        return result

    def dispatch(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Dispatch to a registered tool by name."""
        handler = self.get(name)
        if handler is None:
            raise ToolDispatchError(code="UNKNOWN_TOOL", message=f"Unknown tool: {name}")
        return handler(arguments)
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/unit/test_tool_registry.py -q
```

Expected: `5 passed`

- [ ] **Step 5: Lint, type-check, full suite**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/repo_mcp/tools/registry.py tests/unit/test_tool_registry.py
git commit -m "feat: add ToolMetadata and list_tools() to ToolRegistry for MCP discovery"
```

---

## Task 4: Register Metadata in Builtin Tools

**Files:**
- Modify: `src/repo_mcp/tools/builtin.py`

**Interfaces:**
- Consumes: `ToolMetadata` from `repo_mcp.tools.registry`, `TOOL_SCHEMAS` from `repo_mcp.tools.schemas`
- Produces: `register_builtin_tools` now registers metadata alongside every handler

- [ ] **Step 1: Write the failing test**

Add this test to `tests/unit/tools/test_tool_schemas.py` (append at end of file):

```python
from pathlib import Path

from repo_mcp.server import create_server


def test_builtin_tools_all_have_metadata_registered(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    tools = server._registry.list_tools()
    names = {t["name"] for t in tools}
    assert names == set(EXPECTED_TOOLS)
    for tool in tools:
        assert tool["description"]
        assert tool["inputSchema"]
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/unit/tools/test_tool_schemas.py::test_builtin_tools_all_have_metadata_registered -q
```

Expected: FAIL — `list_tools()` returns `[]` because no metadata is registered yet.

- [ ] **Step 3: Update `src/repo_mcp/tools/builtin.py`**

Add these imports at the top of the existing imports block:

```python
from repo_mcp.tools.registry import ToolDispatchError, ToolHandler, ToolMetadata, ToolRegistry
from repo_mcp.tools.schemas import TOOL_SCHEMAS
```

Remove the old import line:
```python
from repo_mcp.tools.registry import ToolDispatchError, ToolHandler, ToolRegistry
```

Add this helper function near the top of the module (after imports, before `register_builtin_tools`):

```python
def _meta(name: str) -> ToolMetadata:
    schema = TOOL_SCHEMAS[name]
    return ToolMetadata(
        name=name,
        description=str(schema["description"]),
        input_schema=dict(schema["inputSchema"]),  # type: ignore[arg-type]
    )
```

Then update every `registry.register` call in `register_builtin_tools` to pass the metadata:

```python
def register_builtin_tools(
    registry: ToolRegistry,
    repo_root: Path,
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
    list_files: Callable[[dict[str, object]], dict[str, object]],
    refresh_index: Callable[[bool], dict[str, object]],
    read_index_status: Callable[[], IndexStatus],
    search_index: Callable[[str, int, str | None, str | None], list[dict[str, object]]],
    outline_path: Callable[[str], dict[str, object]],
    build_context_bundle: Callable[[dict[str, object]], dict[str, object]],
    resolve_references: Callable[[dict[str, object]], dict[str, object]],
    config: ServerConfig,
) -> None:
    """Register the minimum v1 tool set with deterministic stub behavior."""
    registry.register(
        "repo.status",
        _status_handler(repo_root, limits, config, read_index_status),
        _meta("repo.status"),
    )
    registry.register(
        "repo.list_files",
        _list_files_handler(list_files),
        _meta("repo.list_files"),
    )
    registry.register(
        "repo.open_file",
        _open_file_handler(repo_root, limits),
        _meta("repo.open_file"),
    )
    registry.register(
        "repo.outline",
        _outline_handler(outline_path),
        _meta("repo.outline"),
    )
    registry.register(
        "repo.search",
        _search_handler(limits, search_index),
        _meta("repo.search"),
    )
    registry.register(
        "repo.build_context_bundle",
        _build_context_bundle_handler(build_context_bundle),
        _meta("repo.build_context_bundle"),
    )
    registry.register(
        "repo.references",
        _references_handler(limits, resolve_references),
        _meta("repo.references"),
    )
    registry.register(
        "repo.refresh_index",
        _refresh_index_handler(refresh_index),
        _meta("repo.refresh_index"),
    )
    registry.register(
        "repo.audit_log",
        _audit_log_handler(limits, read_audit_entries),
        _meta("repo.audit_log"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/unit/tools/test_tool_schemas.py -q
```

Expected: `4 passed`

- [ ] **Step 5: Lint, type-check, full suite**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/repo_mcp/tools/builtin.py tests/unit/tools/test_tool_schemas.py
git commit -m "feat: register MCP metadata for all built-in tools"
```

---

## Task 5: MCP Protocol Layer (server.py)

**Files:**
- Modify: `src/repo_mcp/server.py`

**Interfaces:**
- Consumes: `ToolRegistry.list_tools()` (Task 3), `importlib.metadata.version`
- Produces:
  - `StdioServer.handle_json_line(raw_line) -> dict | None` — returns `None` for notifications
  - `StdioServer.handle_payload(payload) -> dict | None` — returns `None` for notifications
  - `StdioServer.jsonrpc_result(id_, result) -> dict` — static method
  - `StdioServer.jsonrpc_error(id_, code, message) -> dict` — static method
  - `StdioServer.tool_content(text) -> dict` — static method
  - `StdioServer.tool_error_content(text) -> dict` — static method
  - `StdioServer._handle_initialize(id_) -> dict`
  - `StdioServer._handle_tools_call(id_, params) -> dict`
  - `StdioServer._log_request(request_id, tool_name, arguments, ok, blocked, error_code) -> None`

> **Note:** This task breaks existing tests. That is expected — Tasks 6–8 fix them.

- [ ] **Step 1: Replace the protocol layer in `src/repo_mcp/server.py`**

**Remove these methods entirely** from `StdioServer` (they are replaced by the new methods below):
- `parse_request`
- `extract_request_id`
- `next_request_id`
- `success_response`
- `error_response`
- `blocked_response`
- `enforce_response_size_limit`
- `log_request`

Also remove the `Request` dataclass (no longer needed).

**Remove this import** (no longer needed):
```python
from dataclasses import asdict, dataclass
```

**Add this import** (needed for version lookup):
```python
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
```

Keep `from dataclasses import asdict` — it is still used in `_bundle_result_to_dict` and `_resolve_references`.

**Replace** `handle_json_line`, `handle_payload`, and `serve` with these new implementations:

```python
def serve(self, in_stream: TextIO, out_stream: TextIO) -> None:
    """Process JSON-line requests from stdin and write JSON-line responses."""
    for raw_line in in_stream:
        line = raw_line.strip()
        if not line:
            continue
        response = self.handle_json_line(line)
        if response is None:
            continue
        out_stream.write(f"{json.dumps(response, sort_keys=True)}\n")
        out_stream.flush()

def handle_json_line(self, raw_line: str) -> dict[str, object] | None:
    """Handle a single JSON-line request. Returns None for notifications."""
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return self.jsonrpc_error(None, -32700, "Parse error: request must be valid JSON.")
    return self.handle_payload(payload)

def handle_payload(self, payload: object) -> dict[str, object] | None:
    """Validate and dispatch a JSON-RPC 2.0 payload. Returns None for notifications."""
    if not isinstance(payload, dict):
        return self.jsonrpc_error(None, -32600, "Invalid Request: must be an object.")

    has_id = "id" in payload
    raw_id = payload.get("id")
    id_: str | int | None
    if isinstance(raw_id, str):
        id_ = raw_id
    elif isinstance(raw_id, int):
        id_ = raw_id
    else:
        id_ = None

    method = payload.get("method")
    params = payload.get("params", {})

    if not isinstance(method, str) or not method:
        if not has_id:
            return None
        return self.jsonrpc_error(id_, -32600, "Invalid Request: method must be a non-empty string.")

    if not isinstance(params, dict):
        if not has_id:
            return None
        return self.jsonrpc_error(id_, -32600, "Invalid Request: params must be an object.")

    if not has_id:
        return None

    if method == "initialize":
        return self._handle_initialize(id_)

    if method == "tools/list":
        return self.jsonrpc_result(id_, {"tools": self._registry.list_tools()})

    if method == "tools/call":
        return self._handle_tools_call(id_, params)

    return self.jsonrpc_error(id_, -32601, f"Method not found: {method}")
```

**Add these static methods** to `StdioServer`:

```python
@staticmethod
def jsonrpc_result(id_: str | int | None, result: dict[str, object]) -> dict[str, object]:
    """Build a JSON-RPC 2.0 success response."""
    return {"id": id_, "jsonrpc": "2.0", "result": result}

@staticmethod
def jsonrpc_error(id_: str | int | None, code: int, message: str) -> dict[str, object]:
    """Build a JSON-RPC 2.0 error response."""
    return {"error": {"code": code, "message": message}, "id": id_, "jsonrpc": "2.0"}

@staticmethod
def tool_content(text: str) -> dict[str, object]:
    """Build a successful MCP tool result with one text content block."""
    return {"content": [{"text": text, "type": "text"}]}

@staticmethod
def tool_error_content(text: str) -> dict[str, object]:
    """Build an isError MCP tool result with one text content block."""
    return {"content": [{"text": text, "type": "text"}], "isError": True}
```

**Add these instance methods** to `StdioServer`:

```python
def _handle_initialize(self, id_: str | int | None) -> dict[str, object]:
    """Respond to the MCP initialize handshake."""
    try:
        ver: str = _pkg_version("repo-interrogator")
    except PackageNotFoundError:
        ver = "0.0.0"
    return self.jsonrpc_result(
        id_,
        {
            "capabilities": {"tools": {}},
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "repo-interrogator", "version": ver},
        },
    )

def _handle_tools_call(
    self, id_: str | int | None, params: dict[str, object]
) -> dict[str, object]:
    """Dispatch a tools/call request and wrap the result in MCP content blocks."""
    tool_name_value = params.get("name")
    arguments_value = params.get("arguments", {})

    if not isinstance(tool_name_value, str) or not tool_name_value:
        return self.jsonrpc_error(
            id_,
            -32602,
            "Invalid params: tools/call name must be a non-empty string.",
        )
    if not isinstance(arguments_value, dict):
        return self.jsonrpc_error(
            id_,
            -32602,
            "Invalid params: tools/call arguments must be an object.",
        )

    tool_name = tool_name_value
    arguments = cast(dict[str, object], arguments_value)

    try:
        result = self._registry.dispatch(name=tool_name, arguments=arguments)
    except PathBlockedError as error:
        self._log_request(
            str(id_), tool_name, arguments, ok=False, blocked=True, error_code="PATH_BLOCKED"
        )
        return self.jsonrpc_result(
            id_, self.tool_error_content(f"Blocked: {error.reason} {error.hint}")
        )
    except PolicyBlockedError as error:
        self._log_request(
            str(id_), tool_name, arguments, ok=False, blocked=True, error_code="POLICY_BLOCKED"
        )
        return self.jsonrpc_result(
            id_, self.tool_error_content(f"Blocked: {error.reason} {error.hint}")
        )
    except ToolDispatchError as error:
        self._log_request(
            str(id_),
            tool_name,
            arguments,
            ok=False,
            blocked=False,
            error_code=error.code,
        )
        return self.jsonrpc_result(
            id_, self.tool_error_content(f"Error ({error.code}): {error.message}")
        )
    except IndexSchemaUnsupportedError as error:
        msg = (
            f"Index schema error: stored schema {error.found!r} is unsupported "
            f"(expected {error.expected!r}). Run repo.refresh_index with force=true."
        )
        self._log_request(
            str(id_),
            tool_name,
            arguments,
            ok=False,
            blocked=False,
            error_code="INDEX_SCHEMA_UNSUPPORTED",
        )
        return self.jsonrpc_result(id_, self.tool_error_content(msg))
    except Exception:
        self._log_request(
            str(id_), tool_name, arguments, ok=False, blocked=False, error_code="INTERNAL_ERROR"
        )
        return self.jsonrpc_error(id_, -32603, "Internal server error.")

    warnings = _extract_result_warnings(result)
    text = json.dumps(result, sort_keys=True)
    content: list[dict[str, object]] = [{"text": text, "type": "text"}]
    for w in warnings:
        content.append({"text": f"Warning: {w}", "type": "text"})

    tool_result: dict[str, object] = {"content": content}
    response = self.jsonrpc_result(id_, tool_result)

    response_bytes = len(json.dumps(response, sort_keys=True).encode("utf-8"))
    if response_bytes > self._limits.max_total_bytes_per_response:
        self._log_request(
            str(id_),
            tool_name,
            arguments,
            ok=False,
            blocked=True,
            error_code="RESPONSE_TOO_LARGE",
        )
        return self.jsonrpc_result(
            id_,
            self.tool_error_content(
                "Response exceeds max_total_bytes_per_response limit. "
                "Request fewer lines or lower result volume."
            ),
        )

    self._log_request(str(id_), tool_name, arguments, ok=True, blocked=False, error_code=None)
    return response

def _log_request(
    self,
    request_id: str,
    tool_name: str,
    arguments: dict[str, object],
    ok: bool,
    blocked: bool,
    error_code: str | None,
) -> None:
    """Append one sanitized audit event."""
    event = AuditEvent(
        timestamp=utc_timestamp(),
        request_id=request_id,
        tool=tool_name,
        ok=ok,
        blocked=blocked,
        error_code=error_code,
        metadata=sanitize_arguments(arguments),
    )
    self._audit_logger.append(event)
```

Also update `self._fallback_request_counter` initialization — remove it from `__init__` since `next_request_id` is gone.

- [ ] **Step 2: Run lint and type-check (tests will fail — that is expected)**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
```

Expected: lint and type-check pass. Tests will fail — that is correct at this step.

- [ ] **Step 3: Commit the protocol rewrite**

```bash
git add src/repo_mcp/server.py
git commit -m "feat: replace custom envelope with MCP JSON-RPC 2.0 protocol"
```

---

## Task 6: Test Helpers and Core Protocol Tests

**Files:**
- Create: `tests/helpers.py`
- Modify: `tests/unit/test_error_envelope.py`
- Create: `tests/integration/test_mcp_protocol.py`
- Modify: `tests/unit/tools/test_blocked_response_shapes.py`
- Modify: `tests/integration/test_stdio_server_smoke.py`

**Interfaces:**
- Consumes: `StdioServer.handle_payload`, `StdioServer.handle_json_line`, `StdioServer.jsonrpc_result`, `StdioServer._handle_initialize`
- Produces:
  - `tests/helpers.call_tool(server, request_id, tool_name, arguments) -> dict`
  - `tests/helpers.extract_result(response) -> dict`
  - `tests/helpers.is_tool_error(response) -> bool`
  - `tests/helpers.tool_error_text(response) -> str`

- [ ] **Step 1: Create `tests/helpers.py`**

```python
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
```

- [ ] **Step 2: Rewrite `tests/unit/test_error_envelope.py`**

```python
from __future__ import annotations

import json

from repo_mcp.server import create_server

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_malformed_json_returns_parse_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_json_line("{not-json")

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] is None
    assert response["error"]["code"] == -32700
    assert "Parse error" in response["error"]["message"]


def test_unknown_method_returns_method_not_found() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": "abc-123", "jsonrpc": "2.0", "method": "repo.unknown", "params": {}}
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "abc-123"
    assert response["error"]["code"] == -32601
    assert "repo.unknown" in response["error"]["message"]


def test_unknown_tool_name_in_tools_call_returns_tool_error() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "abc-456", "repo.nonexistent", {})

    assert is_tool_error(response)
    assert "UNKNOWN_TOOL" in tool_error_text(response)


def test_invalid_tools_call_name_returns_protocol_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": 7,
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "", "arguments": {}},
        }
    )

    assert response is not None
    assert response["id"] == 7
    assert response["error"]["code"] == -32602
    assert "name" in response["error"]["message"]


def test_invalid_tools_call_arguments_returns_protocol_error() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": "bad-args",
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "repo.status", "arguments": []},
        }
    )

    assert response is not None
    assert response["id"] == "bad-args"
    assert response["error"]["code"] == -32602
    assert "arguments" in response["error"]["message"]
```

- [ ] **Step 3: Create `tests/integration/test_mcp_protocol.py`**

```python
from __future__ import annotations

import io
import json

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result

EXPECTED_TOOLS = [
    "repo.status",
    "repo.list_files",
    "repo.open_file",
    "repo.outline",
    "repo.search",
    "repo.build_context_bundle",
    "repo.references",
    "repo.refresh_index",
    "repo.audit_log",
]


def test_initialize_returns_mcp_capabilities() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.0.1"},
            },
        }
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "repo-interrogator"
    assert isinstance(result["serverInfo"]["version"], str)


def test_tools_list_returns_all_nine_tools() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": 2, "jsonrpc": "2.0", "method": "tools/list", "params": {}}
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    tools = response["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == set(EXPECTED_TOOLS)
    for tool in tools:
        assert isinstance(tool["description"], str)
        assert tool["description"]
        assert tool["inputSchema"]["type"] == "object"


def test_notification_produces_no_response() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )

    assert response is None


def test_tools_call_status_returns_content_block() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "tc-1", "repo.status", {})

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "tc-1"
    result = response["result"]
    assert not result.get("isError")
    content = result["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    data = json.loads(content[0]["text"])
    assert "index_status" in data


def test_full_mcp_handshake_and_tool_call() -> None:
    server = create_server(repo_root=".")
    in_lines = [
        json.dumps({"id": 1, "jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
        json.dumps({"id": 2, "jsonrpc": "2.0", "method": "tools/list", "params": {}}),
        json.dumps({"id": 3, "jsonrpc": "2.0", "method": "tools/call", "params": {"name": "repo.status", "arguments": {}}}),
    ]
    in_stream = io.StringIO("\n".join(in_lines) + "\n")
    out_stream = io.StringIO()

    server.serve(in_stream=in_stream, out_stream=out_stream)

    lines = [line for line in out_stream.getvalue().splitlines() if line]
    assert len(lines) == 3  # notification produces no response
    init_resp = json.loads(lines[0])
    list_resp = json.loads(lines[1])
    call_resp = json.loads(lines[2])
    assert init_resp["id"] == 1
    assert init_resp["result"]["protocolVersion"] == "2024-11-05"
    assert list_resp["id"] == 2
    assert len(list_resp["result"]["tools"]) == 9
    assert call_resp["id"] == 3
    assert not call_resp["result"].get("isError")


def test_unknown_method_returns_32601() -> None:
    server = create_server(repo_root=".")

    response = server.handle_payload(
        {"id": "x", "jsonrpc": "2.0", "method": "rpc.discover", "params": {}}
    )

    assert response is not None
    assert response["error"]["code"] == -32601


def test_parse_error_returns_32700() -> None:
    server = create_server(repo_root=".")

    response = server.handle_json_line("{bad json")

    assert response is not None
    assert response["error"]["code"] == -32700
    assert response["id"] is None
```

- [ ] **Step 4: Rewrite `tests/unit/tools/test_blocked_response_shapes.py`**

```python
from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_path_traversal_open_file_returns_is_error(tmp_path: Path) -> None:
    from repo_mcp.server import create_server

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(
        server, "block-1", "repo.open_file", {"path": "../secret.txt", "start_line": 1, "end_line": 3}
    )

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "numbered_lines" not in text


def test_path_traversal_outline_returns_is_error(tmp_path: Path) -> None:
    from repo_mcp.server import create_server

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(server, "block-2", "repo.outline", {"path": "../outside.py"})

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "symbols" not in text
```

- [ ] **Step 5: Rewrite `tests/integration/test_stdio_server_smoke.py`**

```python
from __future__ import annotations

import io
import json

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_stdio_server_routes_multiple_requests() -> None:
    server = create_server(repo_root=".")
    in_stream = io.StringIO(
        "\n".join(
            [
                json.dumps({"id": "req-1", "jsonrpc": "2.0", "method": "tools/call", "params": {"name": "repo.status", "arguments": {}}}),
                json.dumps({"id": "req-2", "jsonrpc": "2.0", "method": "tools/call", "params": {"name": "repo.search", "arguments": {"query": "x"}}}),
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
```

- [ ] **Step 6: Run the new and updated tests**

```
python -m pytest tests/unit/test_error_envelope.py tests/integration/test_mcp_protocol.py tests/unit/tools/test_blocked_response_shapes.py tests/integration/test_stdio_server_smoke.py -q
```

Expected: all pass.

- [ ] **Step 7: Lint, type-check**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add tests/helpers.py tests/unit/test_error_envelope.py tests/integration/test_mcp_protocol.py tests/unit/tools/test_blocked_response_shapes.py tests/integration/test_stdio_server_smoke.py
git commit -m "test: add MCP protocol tests and shared test helpers"
```

---

## Task 7: Update Tool-Specific Unit Tests

**Files:**
- Modify: `tests/unit/security/test_limit_enforcement.py`
- Modify: `tests/unit/security/test_block_not_redact_policy.py`
- Modify: `tests/unit/security/test_path_normalization_cross_platform.py`
- Modify: `tests/unit/search/test_bm25_basic.py`
- Modify: `tests/unit/index/test_force_refresh_behavior.py`
- Modify: `tests/unit/index/test_index_schema_versioning.py`
- Modify: `tests/unit/logging/test_bundle_audit_sanitization.py`
- Modify: `tests/unit/bundler/test_bundle_export_policy.py`

**Transformation pattern for all files:**
- `server.handle_payload({"id": X, "method": "repo.foo", "params": Y})` → `call_tool(server, X, "repo.foo", Y)`
- `response["ok"] is True` → `not is_tool_error(response)`
- `response["ok"] is False` → `is_tool_error(response)` (for tool errors) or `"error" in response` (for protocol errors)
- `response["blocked"] is True` → `is_tool_error(response)`
- `response["result"]["field"]` → `extract_result(response)["field"]`
- `response["error"]["code"] == "SOME_CODE"` → `"SOME_CODE" in tool_error_text(response)`
- `response["error"]["message"]` → `tool_error_text(response)`
- `response["warnings"]` → check content list length > 1 and look for `"Warning:"` in content[1]["text"]
- Add `from tests.helpers import call_tool, extract_result, is_tool_error, tool_error_text` to each file

- [ ] **Step 1: Rewrite `tests/unit/security/test_limit_enforcement.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.security import SecurityLimits
from repo_mcp.server import create_server

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_max_file_bytes_limit_blocks_open_file(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("a" * 20, encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_file_bytes=10))

    response = call_tool(server, "req-large-file", "repo.open_file", {"path": "large.txt", "start_line": 1, "end_line": 1})

    assert is_tool_error(response)
    assert "max_file_bytes" in tool_error_text(response).lower() or "Blocked" in tool_error_text(response)


def test_max_open_lines_limit_blocks_large_range(tmp_path: Path) -> None:
    target = tmp_path / "many_lines.txt"
    target.write_text("1\n2\n3\n4\n5\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_open_lines=2))

    response = call_tool(server, "req-lines", "repo.open_file", {"path": "many_lines.txt", "start_line": 1, "end_line": 5})

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)


def test_max_search_hits_limit_blocks_large_top_k(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_search_hits=3))

    response = call_tool(server, "req-search", "repo.search", {"query": "x", "top_k": 10})

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)


def test_max_total_response_bytes_limit_blocks_oversized_payload(tmp_path: Path) -> None:
    target = tmp_path / "lines.txt"
    target.write_text("a\nb\nc\n", encoding="utf-8")
    server = create_server(
        repo_root=str(tmp_path),
        limits=SecurityLimits(max_total_bytes_per_response=120),
    )

    response = call_tool(server, "req-response-size", "repo.open_file", {"path": "lines.txt", "start_line": 1, "end_line": 3})

    encoded = json.dumps(response, sort_keys=True).encode("utf-8")
    assert is_tool_error(response)
    assert "max_total_bytes_per_response" in tool_error_text(response).lower() or "exceeds" in tool_error_text(response).lower()
    assert len(encoded) <= 1200


def test_max_references_limit_blocks_large_reference_top_k(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_references=2))

    response = call_tool(server, "req-references", "repo.references", {"symbol": "Service.run", "top_k": 10})

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)
```

- [ ] **Step 2: Rewrite `tests/unit/security/test_block_not_redact_policy.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_denylisted_open_file_is_blocked_without_content_leak(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("API_KEY=super-secret-value\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(server, "req-deny", "repo.open_file", {"path": ".env", "start_line": 1, "end_line": 1})

    assert is_tool_error(response)
    assert "super-secret-value" not in str(response)
    assert "numbered_lines" not in str(response)
```

- [ ] **Step 3: Rewrite `tests/unit/security/test_path_normalization_cross_platform.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.security import resolve_repo_path
from repo_mcp.server import create_server

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_windows_separator_path_normalizes_to_same_file(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "main.py"
    py_file.write_text("print('ok')\n", encoding="utf-8")

    resolved = resolve_repo_path(repo_root=tmp_path, candidate=r"src\main.py")

    assert resolved == py_file.resolve()


def test_blocked_open_file_response_does_not_include_file_content() -> None:
    server = create_server(repo_root=".")

    response = call_tool(server, "req-block-1", "repo.open_file", {"path": "../secrets.txt", "start_line": 1, "end_line": 5})

    assert response["id"] == "req-block-1"
    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "Blocked" in text
    assert "Path traversal" in text
```

- [ ] **Step 4: Rewrite `tests/unit/search/test_bm25_basic.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_bm25_basic_returns_relevant_ranked_hits(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "def run_alpha():\n    return 'alpha keyword alpha'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def run_beta():\n    return 'beta keyword'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-bm25-1", "repo.refresh_index", {})

    response = call_tool(server, "req-bm25-2", "repo.search", {"query": "alpha keyword", "mode": "bm25", "top_k": 2})

    hits = extract_result(response)["hits"]
    assert len(hits) == 2
    assert hits[0]["path"] == "src/alpha.py"
    assert hits[0]["score"] >= hits[1]["score"]
    assert "alpha" in hits[0]["matched_terms"]
    assert "keyword" in hits[0]["matched_terms"]
```

- [ ] **Step 5: Rewrite `tests/unit/index/test_force_refresh_behavior.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_force_refresh_rebuilds_when_schema_mismatched(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    index_dir = tmp_path / ".repo_mcp" / "index"
    index_dir.mkdir(parents=True)
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "last_refresh_timestamp": "2026-02-08T00:00:00.000Z",
                "indexed_file_count": 0,
                "indexed_chunk_count": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(server, "req-force", "repo.refresh_index", {"force": True})

    result = extract_result(response)
    assert result["added"] == 1
    assert result["updated"] == 0
    assert result["removed"] == 0

    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["indexed_file_count"] == 1
    assert manifest["indexed_chunk_count"] >= 1
```

- [ ] **Step 6: Rewrite `tests/unit/index/test_index_schema_versioning.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, is_tool_error, tool_error_text


def test_schema_version_mismatch_returns_explicit_error(tmp_path: Path) -> None:
    index_dir = tmp_path / ".repo_mcp" / "index"
    index_dir.mkdir(parents=True)
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 999,
                "last_refresh_timestamp": "2026-02-08T00:00:00.000Z",
                "indexed_file_count": 1,
                "indexed_chunk_count": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (index_dir / "files.jsonl").write_text(
        json.dumps(
            {
                "path": "src/a.py",
                "size": 1,
                "mtime_ns": 1,
                "content_hash": "deadbeef",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(server, "req-schema", "repo.refresh_index", {"force": False})

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "INDEX_SCHEMA_UNSUPPORTED" in text or "schema" in text.lower()
    assert "force=true" in text
```

- [ ] **Step 7: Rewrite `tests/unit/logging/test_bundle_audit_sanitization.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool


def test_bundle_audit_log_sanitizes_prompt_and_budget(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 'a'\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-san-1", "repo.refresh_index", {})
    call_tool(
        server,
        "req-san-2",
        "repo.build_context_bundle",
        {
            "prompt": "API_KEY=super-secret-token",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    audit_path = tmp_path / ".repo_mcp" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    bundle_entries = [e for e in entries if e.get("tool") == "repo.build_context_bundle"]
    assert bundle_entries
    event = bundle_entries[-1]
    metadata = event["metadata"]

    assert metadata["prompt_present"] is True
    assert metadata["prompt_length"] == len("API_KEY=super-secret-token")
    assert "prompt" not in metadata
    assert metadata["budget_type"] == "dict"
    assert metadata["budget_keys"] == ["max_files", "max_total_lines"]
    rendered = json.dumps(event, sort_keys=True)
    assert "super-secret-token" not in rendered
    assert "excerpt" not in rendered
```

- [ ] **Step 8: Rewrite `tests/unit/bundler/test_bundle_export_policy.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result, is_tool_error


def test_bundle_exports_written_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def x():\n    return 'x'\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-exp-1", "repo.refresh_index", {})

    response = call_tool(
        server,
        "req-exp-2",
        "repo.build_context_bundle",
        {
            "prompt": "x return",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    assert not is_tool_error(response)
    content = response["result"]["content"]
    assert len(content) == 1  # no warnings
    assert (tmp_path / ".repo_mcp" / "last_bundle.json").exists()
    assert (tmp_path / ".repo_mcp" / "last_bundle.md").exists()


def test_bundle_export_failure_returns_warning_but_success(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def x():\n    return 'x'\n", encoding="utf-8")
    data_dir = tmp_path / ".repo_mcp"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "last_bundle.json").mkdir()
    (data_dir / "last_bundle.md").mkdir()
    server = create_server(repo_root=str(tmp_path))
    response = call_tool(
        server,
        "req-exp-3",
        "repo.build_context_bundle",
        {
            "prompt": "x return",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    assert not is_tool_error(response)
    content = response["result"]["content"]
    assert len(content) >= 2  # result + at least one warning
    warning_texts = [item["text"] for item in content[1:]]
    assert any("last_bundle" in w for w in warning_texts)
```

- [ ] **Step 9: Run all updated unit tests**

```
python -m pytest tests/unit/security/test_limit_enforcement.py tests/unit/security/test_block_not_redact_policy.py tests/unit/security/test_path_normalization_cross_platform.py tests/unit/search/test_bm25_basic.py tests/unit/index/test_force_refresh_behavior.py tests/unit/index/test_index_schema_versioning.py tests/unit/logging/test_bundle_audit_sanitization.py tests/unit/bundler/test_bundle_export_policy.py -q
```

Expected: all pass.

- [ ] **Step 10: Lint and type-check**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
```

Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add tests/unit/security/ tests/unit/search/ tests/unit/index/test_force_refresh_behavior.py tests/unit/index/test_index_schema_versioning.py tests/unit/logging/test_bundle_audit_sanitization.py tests/unit/bundler/test_bundle_export_policy.py
git commit -m "test: update unit tests for MCP JSON-RPC 2.0 protocol"
```

---

## Task 8: Update Integration Tests

**Files:**
- Modify: `tests/integration/test_tool_contract_matrix.py`
- Modify: `tests/integration/test_stdio_workflow_e2e.py`
- Modify: `tests/integration/test_repo_status_config_snapshot.py`
- Modify: `tests/integration/test_repo_search_tool.py`
- Modify: `tests/integration/test_repo_audit_log_tool.py`
- Modify: `tests/integration/test_repo_outline_tool.py`
- Modify: `tests/integration/test_repo_outline_multilanguage_selection.py`
- Modify: `tests/integration/test_repo_references_tool.py`
- Modify: `tests/integration/test_repo_references_adapter_grouping.py`
- Modify: `tests/integration/test_bundle_with_non_python_outline.py`
- Modify: `tests/integration/test_repo_build_context_bundle_tool.py`

- [ ] **Step 1: Rewrite `tests/integration/test_tool_contract_matrix.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result, is_tool_error


def test_tool_contract_matrix_for_required_v1_tools(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "class Main:\n    def run(self) -> int:\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text("search term\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    # Seed index for search/bundle
    call_tool(server, "req-matrix-seed", "repo.refresh_index", {"force": False})

    tool_calls: list[tuple[str, dict[str, object]]] = [
        ("repo.status", {}),
        ("repo.list_files", {"max_results": 10}),
        ("repo.open_file", {"path": "src/main.py", "start_line": 1, "end_line": 3}),
        ("repo.refresh_index", {"force": False}),
        ("repo.search", {"query": "search", "mode": "bm25", "top_k": 5}),
        ("repo.outline", {"path": "src/main.py"}),
        ("repo.references", {"symbol": "Main.run", "top_k": 5}),
        (
            "repo.build_context_bundle",
            {
                "prompt": "main run search",
                "budget": {"max_files": 2, "max_total_lines": 20},
                "strategy": "hybrid",
                "include_tests": True,
            },
        ),
        ("repo.audit_log", {"limit": 20}),
    ]

    for idx, (tool_name, arguments) in enumerate(tool_calls):
        response = call_tool(server, f"req-matrix-{idx}", tool_name, arguments)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == f"req-matrix-{idx}"
        assert not is_tool_error(response), f"{tool_name} returned isError: {response}"
        result = extract_result(response)

        if tool_name == "repo.search":
            assert "hits" in result
        if tool_name == "repo.outline":
            assert set(result.keys()) == {"path", "language", "symbols"}
            assert result["symbols"]
            assert set(result["symbols"][0].keys()) == {
                "kind",
                "name",
                "signature",
                "start_line",
                "end_line",
                "doc",
                "parent_symbol",
                "scope_kind",
                "is_conditional",
                "decl_context",
            }
        if tool_name == "repo.build_context_bundle":
            assert set(result.keys()) == {
                "bundle_id",
                "prompt_fingerprint",
                "strategy",
                "budget",
                "totals",
                "selections",
                "citations",
                "audit",
            }
            selections = result["selections"]
            assert isinstance(selections, list)
            if selections:
                first = selections[0]
                assert set(first.keys()) == {
                    "path",
                    "start_line",
                    "end_line",
                    "excerpt",
                    "why_selected",
                    "rationale",
                    "score",
                    "source_query",
                }
        if tool_name == "repo.references":
            assert set(result.keys()) == {
                "symbol",
                "references",
                "truncated",
                "total_candidates",
            }
```

- [ ] **Step 2: Rewrite `tests/integration/test_stdio_workflow_e2e.py`**

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def test_stdio_workflow_e2e(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "class App:\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "\n"
        "def parse_token(text: str) -> str:\n"
        "    return text.strip()\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text("token parser workflow\n", encoding="utf-8")

    proc = _start_server(repo_root=tmp_path)
    try:
        # MCP handshake
        init_resp = _send(proc, {"id": 0, "jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "0"}}})
        assert init_resp["result"]["protocolVersion"] == "2024-11-05"
        _send_notification(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        status = _extract(_call_tool(proc, "req-e2e-1", "repo.status", {}))
        assert status["index_status"] == "not_indexed"

        refreshed = _extract(_call_tool(proc, "req-e2e-2", "repo.refresh_index", {"force": False}))
        assert refreshed["added"] == 2

        listed = _extract(_call_tool(proc, "req-e2e-3", "repo.list_files", {"max_results": 10}))
        assert [entry["path"] for entry in listed["files"]] == [
            "docs/guide.md",
            "src/app.py",
        ]

        opened = _extract(_call_tool(proc, "req-e2e-4", "repo.open_file", {"path": "src/app.py", "start_line": 1, "end_line": 3}))
        assert opened["path"] == "src/app.py"
        assert len(opened["numbered_lines"]) == 3

        search_first = _extract(_call_tool(proc, "req-e2e-5", "repo.search", {"query": "token parser", "mode": "bm25", "top_k": 5}))
        search_second = _extract(_call_tool(proc, "req-e2e-6", "repo.search", {"query": "token parser", "mode": "bm25", "top_k": 5}))
        assert search_first["hits"] == search_second["hits"]

        outlined = _extract(_call_tool(proc, "req-e2e-7", "repo.outline", {"path": "src/app.py"}))
        assert outlined["language"] == "python"
        assert [s["name"] for s in outlined["symbols"]] == ["App", "App.run", "parse_token"]

        references = _extract(_call_tool(proc, "req-e2e-8", "repo.references", {"symbol": "App.run", "top_k": 5}))
        assert set(references.keys()) == {"symbol", "references", "truncated", "total_candidates"}

        bundled = _extract(
            _call_tool(
                proc,
                "req-e2e-9",
                "repo.build_context_bundle",
                {
                    "prompt": "token parser",
                    "budget": {"max_files": 2, "max_total_lines": 20},
                    "strategy": "hybrid",
                    "include_tests": True,
                },
            )
        )
        assert bundled["totals"]["selected_files"] >= 1

        audit = _extract(_call_tool(proc, "req-e2e-10", "repo.audit_log", {"limit": 20}))
        tools = [entry["tool"] for entry in audit["entries"]]
        assert "repo.build_context_bundle" in tools
        assert "repo.references" in tools
        assert "repo.search" in tools
    finally:
        _stop_server(proc)


def _start_server(repo_root: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    workspace_root = Path(__file__).resolve().parents[2]
    src_path = workspace_root / "src"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(src_path) if not existing else f"{src_path}:{existing}"
    cmd = [
        sys.executable,
        "-m",
        "repo_mcp.server",
        "--repo-root",
        str(repo_root),
        "--data-dir",
        str(repo_root / ".repo_mcp"),
    ]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _send(proc: subprocess.Popen[str], payload: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON-RPC 2.0 request and read the response."""
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr_output = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"Server produced no response. stderr={stderr_output}")
    return json.loads(line)


def _send_notification(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    """Send a notification (no response expected)."""
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def _call_tool(
    proc: subprocess.Popen[str],
    request_id: str,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, Any]:
    """Send a tools/call request and return the full JSON-RPC 2.0 response."""
    return _send(
        proc,
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    )


def _extract(response: dict[str, Any]) -> dict[str, Any]:
    """Extract the tool result dict from a successful tools/call response."""
    assert "error" not in response, f"JSON-RPC error: {response}"
    result = response["result"]
    assert not result.get("isError"), f"Tool error: {result['content'][0]['text']}"
    return json.loads(result["content"][0]["text"])


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None:
        proc.stdin.close()
    proc.wait(timeout=5)
    if proc.returncode != 0 and proc.stderr is not None:
        stderr_output = proc.stderr.read()
        raise AssertionError(f"Server exited with code {proc.returncode}: {stderr_output}")
```

- [ ] **Step 3: Rewrite `tests/integration/test_repo_status_config_snapshot.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_status_includes_effective_config_snapshot(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_file_bytes = 2048",
                "max_open_lines = 33",
                "max_total_bytes_per_response = 4096",
                "max_search_hits = 12",
                "",
                "[index]",
                'include_extensions = [".py", ".md"]',
                'exclude_globs = ["**/.git/**", "**/.venv/**"]',
                "",
                "[adapters]",
                "python_enabled = false",
            ]
        ),
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    result = extract_result(call_tool(server, "req-status-1", "repo.status", {}))

    assert result["enabled_adapters"] == []
    assert result["limits_summary"] == {
        "max_file_bytes": 2048,
        "max_open_lines": 33,
        "max_total_bytes_per_response": 4096,
        "max_search_hits": 12,
        "max_references": 50,
    }

    effective = result["effective_config"]
    assert effective["repo_root"] == str(tmp_path.resolve())
    assert effective["data_dir"] == str((tmp_path / ".repo_mcp").resolve())
    assert effective["limits"] == result["limits_summary"]
    assert effective["index"]["include_extensions"] == [".py", ".md"]
    assert effective["adapters"]["python_enabled"] is False
```

- [ ] **Step 4: Rewrite `tests/integration/test_repo_search_tool.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_search_tool_returns_structured_hits(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "api.py").write_text(
        "def endpoint():\n    return 'token parser'\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "worker.py").write_text(
        "def worker():\n    return 'queue parser'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-s-1", "repo.refresh_index", {})

    result = extract_result(call_tool(server, "req-s-2", "repo.search", {"query": "parser", "mode": "bm25", "top_k": 5, "file_glob": "pkg/*.py"}))

    hits = result["hits"]
    assert len(hits) == 2
    for hit in hits:
        assert set(hit.keys()) == {
            "path",
            "start_line",
            "end_line",
            "snippet",
            "score",
            "matched_terms",
        }
        assert isinstance(hit["path"], str)
        assert isinstance(hit["start_line"], int)
        assert isinstance(hit["end_line"], int)
        assert isinstance(hit["snippet"], str)
        assert isinstance(hit["score"], float)
        assert isinstance(hit["matched_terms"], list)
```

- [ ] **Step 5: Rewrite `tests/integration/test_repo_audit_log_tool.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_audit_log_returns_recent_sanitized_entries(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    file_path = tmp_path / "app.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    call_tool(server, "req-300", "repo.status", {})
    call_tool(server, "req-301", "repo.open_file", {"path": "app.py", "start_line": 1, "end_line": 1})

    result = extract_result(call_tool(server, "req-302", "repo.audit_log", {"limit": 2}))

    entries = result["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 2

    first = entries[0]
    second = entries[1]

    assert first["request_id"] == "req-300"
    assert first["tool"] == "repo.status"
    assert second["request_id"] == "req-301"
    assert second["tool"] == "repo.open_file"
    assert "print('hello')" not in str(entries)
    assert second["metadata"]["path"] == "app.py"


def test_repo_audit_log_since_filter(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-400", "repo.status", {})

    result = extract_result(call_tool(server, "req-401", "repo.audit_log", {"since": "9999-01-01T00:00:00.000Z"}))

    assert result["entries"] == []
```

- [ ] **Step 6: Rewrite `tests/integration/test_repo_outline_tool.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_outline_tool_uses_python_adapter(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    py_file = tmp_path / "src" / "mod.py"
    py_file.write_text(
        "class A:\n"
        "    def m(self, x: int) -> int:\n"
        "        return x\n"
        "\n"
        "def f(y: str) -> str:\n"
        "    return y\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(call_tool(server, "req-outline-1", "repo.outline", {"path": "src/mod.py"}))

    assert result["language"] == "python"
    assert result["path"] == "src/mod.py"
    names = [symbol["name"] for symbol in result["symbols"]]
    assert names == ["A", "A.m", "f"]
    assert set(result["symbols"][0].keys()) == {
        "kind",
        "name",
        "signature",
        "start_line",
        "end_line",
        "doc",
        "parent_symbol",
        "scope_kind",
        "is_conditional",
        "decl_context",
    }
    assert result["symbols"][0]["scope_kind"] == "module"
    assert result["symbols"][0]["parent_symbol"] is None
    assert result["symbols"][0]["is_conditional"] is False
    assert result["symbols"][1]["scope_kind"] == "class"
    assert result["symbols"][1]["parent_symbol"] == "A"
    assert result["symbols"][2]["scope_kind"] == "module"
```

- [ ] **Step 7: Rewrite `tests/integration/test_repo_outline_multilanguage_selection.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_repo_outline_selects_expected_adapter_by_extension(tmp_path: Path) -> None:
    _write_file(tmp_path / "src" / "mod.py", "def f(x: int) -> int:\n    return x\n")
    _write_file(tmp_path / "src" / "mod.ts", "export function build(name: string) { return name; }\n")
    _write_file(tmp_path / "src" / "mod.js", "function run(v) { return v; }\n")
    _write_file(tmp_path / "src" / "Mod.java", "public class Mod { public int run(int v) { return v; } }\n")
    _write_file(tmp_path / "src" / "mod.go", "package mod\nfunc Build() int { return 1 }\n")
    _write_file(tmp_path / "src" / "mod.rs", "pub fn run(v: i32) -> i32 { v }\n")
    _write_file(tmp_path / "src" / "mod.cpp", "class Mod { public: int run(int v); };\nint parse(int v) { return v; }\n")
    _write_file(tmp_path / "src" / "Mod.cs", "namespace Acme;\npublic class Mod { public int Run(int v) { return v; } }\n")
    _write_file(tmp_path / "docs" / "notes.md", "# Notes\n")

    server = create_server(repo_root=str(tmp_path))

    expected = {
        "src/mod.py": "python",
        "src/mod.ts": "ts_js_lexical",
        "src/mod.js": "ts_js_lexical",
        "src/Mod.java": "java_lexical",
        "src/mod.go": "go_lexical",
        "src/mod.rs": "rust_lexical",
        "src/mod.cpp": "cpp_lexical",
        "src/Mod.cs": "csharp_lexical",
        "docs/notes.md": "lexical",
    }

    for index, (path, language) in enumerate(expected.items(), start=1):
        result = extract_result(call_tool(server, f"req-outline-multi-{index}", "repo.outline", {"path": path}))
        assert result["path"] == path
        assert result["language"] == language

        if language == "lexical":
            assert result["symbols"] == []
        else:
            assert isinstance(result["symbols"], list)
            assert len(result["symbols"]) >= 1
            for symbol in result["symbols"]:
                if language != "python":
                    assert symbol["scope_kind"] in {"module", "class"}
                    if symbol["scope_kind"] == "class":
                        assert symbol["parent_symbol"] is not None
```

- [ ] **Step 8: Rewrite `tests/integration/test_repo_references_tool.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_references_tool_returns_deterministic_structured_payload(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from service import Service\n\nsvc = Service()\nsvc.run()\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "service.ts").write_text(
        "export class Service { run(input: string): string { return input; } }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.ts").write_text(
        'import { Service } from "./service";\nconst svc = new Service();\nsvc.run("ok");\n',
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    first = extract_result(call_tool(server, "req-ref-1", "repo.references", {"symbol": "Service.run", "top_k": 10}))
    second = extract_result(call_tool(server, "req-ref-2", "repo.references", {"symbol": "Service.run", "top_k": 10}))

    assert first == second
    assert set(first.keys()) == {"symbol", "references", "truncated", "total_candidates"}
    assert first["symbol"] == "Service.run"
    assert isinstance(first["references"], list)
    assert first["total_candidates"] == len(first["references"])
    assert first["truncated"] is False

    if first["references"]:
        first_ref = first["references"][0]
        assert set(first_ref.keys()) == {
            "symbol",
            "path",
            "line",
            "kind",
            "evidence",
            "strategy",
            "confidence",
        }


def test_repo_references_tool_path_scope_and_truncation(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text(
        "const svc = new Service();\nsvc.run('a');\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "b.ts").write_text(
        "const svc = new Service();\nsvc.run('b');\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    scoped = extract_result(call_tool(server, "req-ref-scope-1", "repo.references", {"symbol": "Service.run", "path": "src/a.ts", "top_k": 10}))
    assert scoped["references"]
    assert {item["path"] for item in scoped["references"]} == {"src/a.ts"}

    truncated = extract_result(call_tool(server, "req-ref-scope-2", "repo.references", {"symbol": "Service.run", "top_k": 1}))
    assert truncated["truncated"] is True
    assert truncated["total_candidates"] >= 2
    assert len(truncated["references"]) == 1


def test_repo_references_skips_excluded_dirs_and_non_indexed_extensions(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "src" / "api.ts").write_text(
        "export class Api { run(): void {} }\nconst api = new Api();\napi.run();\n",
        encoding="utf-8",
    )
    (tmp_path / ".pytest_cache" / "noise.ts").write_text(
        "const api = new Api();\napi.run();\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text(
        "Api.run Api.run Api.run\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(call_tool(server, "req-ref-filter-1", "repo.references", {"symbol": "Api.run", "top_k": 50}))

    paths = [item["path"] for item in result["references"]]
    assert all(path == "src/api.ts" for path in paths)
```

- [ ] **Step 9: Rewrite `tests/integration/test_repo_references_adapter_grouping.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_references_calls_python_resolver_once_per_request(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "alpha.py").write_text(
        "def target():\n    return 1\n\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    (src / "beta.py").write_text(
        "from alpha import target\n\n\ndef another():\n    return target()\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-ref-group-refresh", "repo.refresh_index", {})

    adapter = server._adapters.select("src/alpha.py")
    original_single = adapter.references_for_symbol
    original_many = getattr(adapter, "references_for_symbols", None)
    single_calls = 0
    many_calls = 0

    def wrapped(symbol: str, files: list[tuple[str, str]], *, top_k: int | None = None):
        nonlocal single_calls
        single_calls += 1
        return original_single(symbol, files, top_k=top_k)

    def wrapped_many(symbols: list[str], files: list[tuple[str, str]], *, top_k: int | None = None):
        nonlocal many_calls
        many_calls += 1
        assert callable(original_many)
        return original_many(symbols, files, top_k=top_k)

    adapter.references_for_symbol = wrapped  # type: ignore[method-assign]
    if callable(original_many):
        adapter.references_for_symbols = wrapped_many  # type: ignore[method-assign]

    call_tool(server, "req-ref-group-1", "repo.references", {"symbol": "target", "top_k": 20})

    assert single_calls + many_calls == 1
```

- [ ] **Step 10: Rewrite `tests/integration/test_bundle_with_non_python_outline.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_bundle_uses_non_python_outline_when_available(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "repo_mcp.toml").write_text(
        '[index]\ninclude_extensions = [".ts"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "mod.ts").write_text(
        "export function buildService(name: string) {\n  return name.trim();\n}\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-bundle-np-1", "repo.refresh_index", {"force": True})

    result = extract_result(
        call_tool(
            server,
            "req-bundle-np-2",
            "repo.build_context_bundle",
            {
                "prompt": "buildService",
                "budget": {"max_files": 1, "max_total_lines": 20},
                "strategy": "hybrid",
                "include_tests": True,
            },
        )
    )

    selections = result["selections"]
    assert len(selections) >= 1
    first = selections[0]
    assert first["path"] == "src/mod.ts"
    assert "aligned_symbol=buildService" in first["rationale"]
```

- [ ] **Step 11: Rewrite `tests/integration/test_repo_build_context_bundle_tool.py`**

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server

from tests.helpers import call_tool, extract_result


def test_repo_build_context_bundle_tool_returns_structured_payload(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "def alpha_parser():\n    return 'parse alpha tokens'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def beta_parser():\n    return 'parse beta tokens'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-bundle-1", "repo.refresh_index", {})

    result = extract_result(
        call_tool(
            server,
            "req-bundle-2",
            "repo.build_context_bundle",
            {
                "prompt": "parser tokens",
                "budget": {"max_files": 2, "max_total_lines": 10},
                "strategy": "hybrid",
                "include_tests": True,
            },
        )
    )

    assert result["strategy"] == "hybrid"
    assert result["budget"] == {"max_files": 2, "max_total_lines": 10}
    assert set(result.keys()) == {
        "bundle_id",
        "prompt_fingerprint",
        "strategy",
        "budget",
        "totals",
        "selections",
        "citations",
        "audit",
    }
    assert isinstance(result["selections"], list)
    assert isinstance(result["citations"], list)
    assert set(result["audit"].keys()) == {
        "search_queries",
        "dedupe_counts",
        "budget_enforcement",
        "ranking_debug",
        "selection_debug",
    }
```

- [ ] **Step 12: Run all updated integration tests**

```
python -m pytest tests/integration/ -q
```

Expected: all pass (except any unrelated pre-existing failures).

- [ ] **Step 13: Run the full test suite**

```
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 14: Lint and type-check**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
```

Expected: all pass.

- [ ] **Step 15: Commit**

```bash
git add tests/integration/
git commit -m "test: update all integration tests for MCP JSON-RPC 2.0 protocol"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `docs/AI_INTEGRATION.md`

- [ ] **Step 1: Replace `docs/AI_INTEGRATION.md`**

Replace the full content with the following:

```markdown
# AI Integration (MCP over STDIO)

This guide explains how to connect standard MCP clients to Repo Interrogator.

## Protocol

Repo Interrogator implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) over STDIO using JSON-RPC 2.0. Standard MCP clients (Claude Desktop, Claude Code, Cursor, and others) connect out of the box without any custom configuration.

## Launch Command

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

Or via module form:

```bash
python -m repo_mcp.server --repo-root /absolute/path/to/target/repo
```

Optional flags:
- `--data-dir` — where to store index, audit log, and bundle artifacts
- `--max-file-bytes` — cap on single file read size
- `--max-open-lines` — cap on lines read per `repo.open_file` call
- `--max-total-bytes-per-response` — cap on total response size
- `--max-search-hits` — cap on `top_k` for search and audit log
- `--max-references` — cap on `top_k` for references
- `--python-adapter-enabled true|false` — enable/disable AST-based Python analysis

## MCP Handshake

Standard clients handle this automatically. The sequence is:

1. Client → `initialize` — negotiates protocol version and capabilities
2. Server → returns `protocolVersion: "2024-11-05"`, `capabilities: {tools: {}}`, `serverInfo`
3. Client → `notifications/initialized` — server silently acknowledges
4. Client → `tools/list` — server returns all 9 tool definitions with JSON Schema
5. Client → `tools/call` — invoke a tool; result is a text content block containing JSON

## Client Setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "my-project": {
      "command": "repo-mcp",
      "args": ["--repo-root", "/absolute/path/to/your/project"]
    }
  }
}
```

If `repo-mcp` is not on PATH, use the full path to the executable or replace `command` with `python` and `args` with `["-m", "repo_mcp.server", "--repo-root", "..."]`.

### Claude Code (claude.ai/code)

Add to `.claude/settings.json` in your project:

```json
{
  "mcpServers": {
    "repo-interrogator": {
      "command": "repo-mcp",
      "args": ["--repo-root", "."]
    }
  }
}
```

### Cursor

Open Cursor settings → MCP → Add server:
- Command: `repo-mcp`
- Args: `["--repo-root", "/absolute/path/to/your/project"]`
- Transport: `stdio`

### Any MCP Client (generic)

Configure a subprocess MCP server with:
- Command: `repo-mcp`
- Args: `["--repo-root", "/absolute/path/to/your/project"]`
- Transport: `stdio`

The client will discover tools automatically via `tools/list`.

## Available Tools

All 9 tools are discovered automatically by the client. Descriptions and JSON Schema are served via `tools/list`.

| Tool | Purpose |
|------|---------|
| `repo.status` | Check index state, limits, and config — call this first |
| `repo.refresh_index` | Build or refresh the BM25 search index |
| `repo.search` | BM25 full-text search over indexed files |
| `repo.open_file` | Read a line range from a file |
| `repo.outline` | Get class/function/symbol structure of a file |
| `repo.references` | Find cross-file usages of a named symbol |
| `repo.build_context_bundle` | Compact, ranked, cited excerpt set for a coding task |
| `repo.list_files` | List files under the repository root |
| `repo.audit_log` | Read sanitized log of all tool calls in this session |

## Recommended Workflow for AI Clients

Add this to your system prompt or project instructions:

```text
Use Repo Interrogator tools before making assumptions about the codebase.
1. Call repo.status to confirm the server is connected.
2. Call repo.refresh_index if the index is not yet built.
3. Use repo.search to locate relevant files, then repo.open_file for exact lines.
4. Use repo.outline for class/function structure and repo.references for cross-file usage.
5. For larger tasks, call repo.build_context_bundle with a prompt and budget — it returns compact cited context with why_selected explanations.
If a tool response contains isError: true, report the error text to the user rather than guessing.
```

## Default Discovery Filters

The index and reference finder skip common noise directories automatically:

- `.git`, `.github`, `.repo_mcp`
- `__pycache__`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.nox`
- `node_modules`, `.next`, `.nuxt`, `dist`, `build`, `target`, `bin`, `obj`, `out`, `coverage`, `tmp`

If your project stores source files in an excluded path, override with `index.exclude_globs` in `repo_mcp.toml`.

## Error Handling

- Tool errors (blocked paths, invalid params, index not built) are returned as `isError: true` content blocks — the AI client sees a human-readable message.
- Protocol errors (unknown methods, parse errors) are returned as JSON-RPC error objects.
- `blocked: true` on a path means access was denied by the security policy — do not attempt to infer the blocked content.

## Performance Checklist

- Call `repo.status` first and check `index_status` — if not `ready`, run `repo.refresh_index`.
- Use `top_k` to bound search and reference result sizes.
- Use `repo.references` with `path` to scope to a single file when possible.
- Use strict `budget` values in `repo.build_context_bundle` to avoid oversized responses.
- Keep `index.exclude_globs` tuned to exclude build/cache/tooling directories.
```

- [ ] **Step 2: Run full suite to confirm nothing broke**

```
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add docs/AI_INTEGRATION.md
git commit -m "docs: update AI_INTEGRATION.md for MCP JSON-RPC 2.0 compliance"
```

---

## Self-Review

### Spec Coverage

- MCP `initialize` handshake → Task 5, tested in Task 6
- `tools/list` discovery → Tasks 2–4, tested in Task 6
- `tools/call` content blocks → Task 5, tested in Tasks 6–8
- Notifications silently ignored → Task 5, tested in Task 6
- `isError` for tool errors (blocks, dispatch errors, schema mismatch) → Task 5, tested in Task 7
- JSON-RPC 2.0 error codes for protocol errors → Task 5, tested in Task 6
- Audit log continues to record all tool calls → Task 5, tested in Task 7
- Response size limit still enforced → Task 5, tested in Task 7
- Warning-on-export preserved → Task 7 (`test_bundle_export_policy`)
- ADR created → Task 1

### Placeholder Scan

No TBDs, TODOs, "similar to", or undescribed steps are present.

### Type Consistency

- `ToolMetadata` defined in Task 3, used in Tasks 4 and 6
- `TOOL_SCHEMAS` defined in Task 2, used in Task 4
- `call_tool` / `extract_result` / `is_tool_error` / `tool_error_text` defined in Task 6, used in Tasks 7–8
- `jsonrpc_result` / `jsonrpc_error` / `tool_content` / `tool_error_content` defined in Task 5, used in all server tests
- `_log_request` defined in Task 5, called in `_handle_tools_call` (same task)
