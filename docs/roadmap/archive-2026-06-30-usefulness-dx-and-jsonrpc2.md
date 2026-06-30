# Archive: Usefulness/DX Wave + MCP JSON-RPC 2.0 Compliance

Date archived: 2026-06-30

This file records items moved out of active `TODO.md` after the usefulness/DX
wave (decided and completed February 2026, but left unarchived in `TODO.md`)
and the MCP JSON-RPC 2.0 protocol compliance effort (completed June 2026,
never tracked in `TODO.md`).

## Completed roadmap items: usefulness/DX wave (Feb 2026)

- [x] `USE-DEC-001` Confirmed `why_not_selected` location/shape: `repo.build_context_bundle.result.audit.selection_debug.why_not_selected_summary`.
- [x] `USE-DEC-002` Confirmed preset naming for recommended config profiles: `small`, `medium`, `large`.
- [x] `USE-DEC-003` Confirmed CI guardrail scope: optional warning-only local/CI command.
- [x] `USE-SPEC-001` Updated `SPEC.md` with usefulness enhancements scope (`why_not_selected` contract, preset guidance, workflow example expectations).
- [x] `USE-ADR-001` Added `ADR-0016` for bounded retrieval explainability extensions and non-goals.
- [x] `USE-QA-001` Added quality golden fixtures for difficult prompts (context relevance stability).
- [x] `USE-OBS-001` Implemented bounded deterministic `why_not_selected` summary for top skipped bundle candidates.
- [x] `USE-DOC-001` Added recommended setup presets and tuning guidance to `docs/CONFIG.md` and `examples/repo_mcp.toml`.
- [x] `USE-PERF-001` Added baseline perf check command docs/usage pattern to `docs/PERFORMANCE_PLAYBOOK.md`.
- [x] `USE-CI-001` Added optional non-blocking CI/local check wiring for perf drift.
- [x] `USE-DOC-002` Added end-to-end LLM workflow recipes to `docs/USAGE.md` and `docs/AI_INTEGRATION.md` (bug investigation, refactor impact analysis, API/data-flow tracing).
- [x] `USE-TEST-001` Added integration tests to keep docs/examples aligned with live tool contract fields.
- [x] `USE-ADR-002` Reviewed: no new ADR required — `ADR-0016` already covers CI guidance and preset strategy.
- [x] `DX-001` Added maintainership automation for changelog/release notes (`CHANGELOG.md`, `docs/release.md`, `.repo_mcp/release_notes.md`).
- [x] `DX-002` Added issue labels/triage docs for single-maintainer workflow (`docs/TRIAGE.md`).

## Completed roadmap items: MCP JSON-RPC 2.0 compliance (Jun 2026)

Not previously tracked in `TODO.md` — done as a dedicated branch
(`feat/mcp-jsonrpc2-compliance`) driven directly by `ADR-0017`.

- [x] Added `ADR-0017` for MCP JSON-RPC 2.0 protocol compliance scope/rationale.
- [x] Added MCP tool schema definitions for `tools/list` discovery.
- [x] Added `ToolMetadata` and `list_tools()` to `ToolRegistry` for MCP discovery.
- [x] Registered MCP metadata for all 9 built-in tools.
- [x] Replaced the proprietary `{ok, result, blocked, warnings, request_id}` envelope with full JSON-RPC 2.0 (`initialize`, `notifications/initialized`, `tools/list`, `tools/call`).
- [x] Updated unit, integration, and cross-platform tests for the new protocol; added shared `tests/helpers.py`.
- [x] Updated `README.md`, `SPEC.md`, `docs/USAGE.md`, `docs/AI_INTEGRATION.md` for JSON-RPC 2.0 protocol and removed stale references to the pre-compliance envelope.

## Outcome summary

- Usefulness/DX wave: explainability (`why_not_selected`), config presets, perf drift guardrails, LLM workflow recipes, and single-maintainer release/triage docs landed and remain in active use; no follow-up gaps found.
- JSON-RPC 2.0 wave: server is now directly compatible with standard MCP clients (Claude Desktop, Claude Code, Cursor) via `initialize` → `tools/list` → `tools/call`; the old direct-method protocol was removed entirely (no backward-compat shim, by design — zero external users at time of change).
