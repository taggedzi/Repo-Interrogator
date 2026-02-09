# TODO

This file is the active roadmap index.

For historical detail, see:
- `docs/roadmap/archive-2026-02-09-implementation-plan.md`

## How to use this file

- Keep items short (one line each).
- Put implementation details in GitHub issues.
- Put behavior contracts in `SPEC.md`.
- Put design decisions in `docs/adr/`.
- Move completed items from `Now`/`Next` to `Done (recent)`.

## Now

- [ ] `V2.5-REF-001` Define deterministic cross-file reference contract in `SPEC.md` (fields, ordering, limits).
- [ ] `V2.5-REF-002` Add ADR for cross-file references scope and non-goals.
- [ ] `V2.5-REF-003` Implement Python reference extraction (definition -> usage links, deterministic ordering).
- [ ] `V2.5-RANK-001` Define deterministic bundle ranking signals and tie-break rules in `SPEC.md`.
- [ ] `V2.5-RANK-002` Emit `why_selected` explanations for bundle selections.
- [ ] `V2.5-TEST-001` Add golden tests for reference output and ranking stability.

## Next

- [ ] `V2.5-REF-004` Add lexical cross-file reference fallback for TS/JS/Java/Go/Rust/C++/C#.
- [ ] `V2.5-REF-005` Add optional `repo.references` tool or equivalent response extension (finalize contract first).
- [ ] `V2.5-RANK-003` Improve ranking with symbol/usage proximity across files.
- [ ] `V2.5-OBS-001` Add bundle/ranking audit fields for explainability debugging.
- [ ] `V2.5-DOC-001` Update `docs/USAGE.md` and `docs/AI_INTEGRATION.md` with v2.5 examples.

## Later

- [ ] `PERF-001` Measure and optimize index/search performance on larger repositories.
- [ ] `DX-001` Add maintainership automation for changelog/release notes.
- [ ] `DX-002` Add issue labels/triage docs for single-maintainer workflow.

## Icebox

- [ ] `ENH-TS-001` Optional enhanced parsing path for TS/JS (only with explicit dependency and ADR approval).
- [ ] `ENH-JAVA-001` Optional enhanced parsing path for Java (same gating).
- [ ] `ENH-OTHERS-001` Optional enhanced parsing path for Go/Rust/C++/C# (same gating).

## Done (recent)

- [x] `V2-OUTLINE-001` Declaration-based outline semantics for Python nested/conditional declarations.
- [x] `V2-OUTLINE-002` Added optional symbol metadata fields: `parent_symbol`, `scope_kind`, `is_conditional`, `decl_context`.
- [x] `V2-OUTLINE-003` Wired v2 metadata through `repo.outline` responses.
- [x] `V2-OUTLINE-004` Aligned non-Python adapters to optional metadata via deterministic inference.
- [x] `DOC-001` Added/updated contributor and security/community templates (`CONTRIBUTING.md`, `SECURITY.md`, issue/PR templates).
- [x] `DOC-002` Updated `docs/USAGE.md` and `docs/AI_INTEGRATION.md` for v2 outline fields/semantics.

## Notes

- If an item changes tool schemas or determinism guarantees, create/update ADR first.
- For major scope changes, add a brief milestone section in `SPEC.md`.
