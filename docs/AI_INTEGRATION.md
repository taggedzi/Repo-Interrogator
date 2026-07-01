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
4. Client → `tools/list` — server returns all 10 tool definitions with JSON Schema
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

All 10 tools are discovered automatically by the client. Descriptions and JSON Schema are served via `tools/list`.

| Tool | Purpose |
|------|---------|
| `repo.status` | Check index state, limits, and config — call this first |
| `repo.refresh_index` | Build or refresh the BM25 search index |
| `repo.search` | BM25 full-text search over indexed files |
| `repo.open_file` | Read a line range from a file |
| `repo.outline` | Get class/function/symbol structure of a file |
| `repo.references` | Find cross-file usages of a named symbol |
| `repo.find_definition` | Find where a symbol is declared |
| `repo.build_context_bundle` | Compact, ranked, cited excerpt set for a coding task |
| `repo.list_files` | List files under the repository root |
| `repo.audit_log` | Read sanitized log of all tool calls in this session |

`repo.search` and `repo.build_context_bundle` support optional semantic/hybrid
retrieval modes when the `semantic` install extra is present — see `docs/USAGE.md`.

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
