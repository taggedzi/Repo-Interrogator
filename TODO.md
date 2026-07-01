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

- Server now speaks MCP-compliant JSON-RPC 2.0 (`ADR-0017`); `feat/mcp-jsonrpc2-compliance` merged via PR #1.
- `repo.find_definition` and Python `read`/`write` reference kinds landed (2026-07-01).
- Optional semantic/hybrid search landed (2026-07-01, `ADR-0018`): `repo.search` `mode`, `repo.build_context_bundle` `retrieval_mode`, `repo.status` `semantic_*` fields. Core package stays zero-dependency; feature is inert without the `[semantic]` extra. **Not yet functional end-to-end** — `DEFAULT_MODEL_SPEC` in `src/repo_mcp/semantic/model_cache.py` ships as an unpinned placeholder; `mode="semantic"`/`"hybrid"` fails closed with an explicit error until a maintainer manually resolves and checksums a real model (see `ADR-0018`'s Known Limitation note).
- Preserve current reliability/determinism while improving usefulness for LLM repository interrogation.
- Avoid changes that materially increase fragility or hidden complexity.

## Decision Gates (ask before implementation)

_None open._

## Now

_None open._

## Next

- Pin a real embedding model for `DEFAULT_MODEL_SPEC` (resolve commit SHA, download, compute SHA256, replace placeholder values — steps documented in `src/repo_mcp/semantic/model_cache.py`) so semantic/hybrid search actually works.

## Later

- Semantic search fast-follows (all deferred as Minor by final review, non-blocking): drop vestigial `Embedder._max_tokens`; assert `vectors.jsonl` on-disk sort order in `test_vector_store.py`; skip `VectorStore.refresh`'s disk rewrite when nothing changed; align `manager.py`'s unreachable bare `ValueError` (unsupported search mode) to the `SemanticNotAvailableError`/`ToolDispatchError` pattern.

## Icebox

_None open. Enhanced (parser-backed) outline paths for TS/JS, Java, Go/Rust/C++/C# were considered and dropped (2026-06-30): no demonstrated need beyond the lexical adapters, and ADR-0009's revisit triggers aren't met. See `ADR-0009` if this resurfaces._

## Notes

- Any schema/contract changes require `SPEC.md` update first.
- Any architectural or policy-level decision requires ADR update/addition.
- Keep all outputs deterministic and bounded.
