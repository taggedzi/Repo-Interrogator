# Archive: v2.5 + Perf Completed

Date archived: 2026-02-10

This file records items moved out of active `TODO.md` after v2.5 references/ranking and performance waves were completed.

## Completed roadmap items

- [x] `V2-OUTLINE-001` Declaration-based outline semantics for Python nested/conditional declarations.
- [x] `V2-OUTLINE-002` Added optional symbol metadata fields: `parent_symbol`, `scope_kind`, `is_conditional`, `decl_context`.
- [x] `V2-OUTLINE-003` Wired v2 metadata through `repo.outline` responses.
- [x] `V2-OUTLINE-004` Aligned non-Python adapters to optional metadata via deterministic inference.

- [x] `V2.5-REF-001` Defined deterministic cross-file references contract in `SPEC.md`.
- [x] `V2.5-REF-002` Added ADR-0013 for deterministic cross-file references scope/non-goals.
- [x] `V2.5-REF-003` Implemented Python AST-based reference extraction/linking.
- [x] `V2.5-REF-004` Added lexical cross-file reference fallback for TS/JS/Java/Go/Rust/C++/C#.
- [x] `V2.5-REF-005` Added `repo.references` tool contract and implementation.

- [x] `V2.5-RANK-001` Defined deterministic bundle ranking signals/tie-break rules in `SPEC.md`.
- [x] `V2.5-RANK-002` Added `why_selected` explanations for bundle selections.
- [x] `V2.5-RANK-003` Improved ranking with symbol/usage proximity across files.
- [x] `V2.5-OBS-001` Added bundle/ranking debug audit fields for explainability.

- [x] `V2.5-TEST-001` Added/updated golden tests for references and ranking stability.
- [x] `V2.5-DOC-001` Updated `docs/USAGE.md` and `docs/AI_INTEGRATION.md` with v2.5 examples.

- [x] `PERF-001` Added opt-in workflow profiling artifacts and optional cProfile capture.
- [x] `PERF-002` Added multi-scenario benchmark runner with retention and session artifacts.
- [x] `PERF-003` Added targeted `repo.references` profiling metrics.
- [x] `PERF-004` Added targeted bundler profiling metrics.
- [x] `PERF-005` Added profiling summary docs/playbook.
- [x] `PERF-006` Added optional non-blocking perf drift guardrails.

- [x] `DOC-001` Added/updated contributor and security/community templates.
- [x] `DOC-002` Updated usage/integration docs for v2 outline semantics.

## Outcome summary

- Deterministic tool contracts preserved.
- Explainability and reference capabilities expanded.
- Performance reduced from multi-minute class runs to single-digit/low-double-digit seconds in benchmark workflows.
- Contract/integration validation remained passing during optimization waves.
