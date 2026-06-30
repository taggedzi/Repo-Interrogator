# TODO

This file is the active roadmap index.

For historical detail, see:
- `docs/roadmap/archive-2026-02-09-implementation-plan.md`
- `docs/roadmap/archive-2026-02-10-v25-and-perf-completed.md`
- `docs/roadmap/archive-2026-06-30-usefulness-dx-and-jsonrpc2.md`

## How to use this file

- Keep items short and execution-scoped.
- Keep this file as the primary active tracker.
- Review `AGENTS.md`, `SPEC.md`, and relevant `docs/adr/*.md` before each item.
- Put behavior/tool contracts in `SPEC.md`.
- Put architectural decisions in `docs/adr/`.
- Move completed items to a dated file in `docs/roadmap/`.

## Current Focus

- Server now speaks MCP-compliant JSON-RPC 2.0 (`ADR-0017`); `feat/mcp-jsonrpc2-compliance` is ready to merge/PR.
- Preserve current reliability/determinism while improving usefulness for LLM repository interrogation.
- Avoid changes that materially increase fragility or hidden complexity.

## Decision Gates (ask before implementation)

_None open._

## Now

_None open._

## Next

_None open._

## Later

_None open._

## Icebox

- [ ] `ENH-TS-001` Optional enhanced parsing path for TS/JS (only with explicit dependency and ADR approval).
- [ ] `ENH-JAVA-001` Optional enhanced parsing path for Java (same gating).
- [ ] `ENH-OTHERS-001` Optional enhanced parsing path for Go/Rust/C++/C# (same gating).

## Notes

- Any schema/contract changes require `SPEC.md` update first.
- Any architectural or policy-level decision requires ADR update/addition.
- Keep all outputs deterministic and bounded.
