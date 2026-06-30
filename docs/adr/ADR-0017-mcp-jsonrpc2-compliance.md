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
