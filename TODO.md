# TODO

This file is the active roadmap index.

For historical detail, see:
- `docs/roadmap/archive-2026-02-09-implementation-plan.md`
- `docs/roadmap/archive-2026-02-10-v25-and-perf-completed.md`

## How to use this file

- Keep items short and execution-scoped.
- Keep this file as the primary active tracker.
- Review `AGENTS.md`, `SPEC.md`, and relevant `docs/adr/*.md` before each item.
- Put behavior/tool contracts in `SPEC.md`.
- Put architectural decisions in `docs/adr/`.
- Move completed items to a dated file in `docs/roadmap/`.

## Current Focus

- Preserve current reliability/determinism while improving usefulness for LLM repository interrogation.
- Avoid changes that materially increase fragility or hidden complexity.

## Decision Gates (ask before implementation)

- [x] `USE-DEC-001` Confirm location/shape for `why_not_selected`:
  - Option A: `repo.build_context_bundle.result.audit.selection_debug.why_not_selected_summary` (recommended).
  - Option B: separate debug-only tool payload.
- [x] `USE-DEC-002` Confirm preset naming for recommended config profiles:
  - Option A: `small`, `medium`, `large` (recommended).
  - Option B: `local_fast`, `balanced`, `deep_context`.
- [x] `USE-DEC-003` Confirm CI guardrail scope:
  - Option A: optional warning-only local/CI command (recommended).
  - Option B: required CI warning job.

## Now

- [x] `USE-SPEC-001` Update `SPEC.md` with usefulness enhancements scope:
  - add bounded `why_not_selected` summary contract (debug/audit only),
  - add recommended config preset guidance (non-binding),
  - add workflow example expectation section.
- [x] `USE-ADR-001` Add ADR for bounded retrieval explainability extensions (`why_not_selected`) and non-goals.
- [x] `USE-QA-001` Add quality golden fixtures for difficult prompts to validate context relevance stability (not just schema/order).
- [x] `USE-OBS-001` Implement bounded deterministic `why_not_selected` summary for top skipped bundle candidates.
- [x] `USE-DOC-001` Add recommended setup presets and tuning guidance to `docs/CONFIG.md` and `examples/repo_mcp.toml`.

## Next

- [ ] `USE-PERF-001` Add baseline perf check command docs and usage pattern (warning-only drift checks) to `docs/PERFORMANCE_PLAYBOOK.md`.
- [ ] `USE-CI-001` Add optional non-blocking CI/local check wiring for perf drift using existing benchmark guardrails.
- [ ] `USE-DOC-002` Add 2-3 end-to-end “LLM workflow recipes” in `docs/USAGE.md` and `docs/AI_INTEGRATION.md`:
  - bug investigation,
  - refactor impact analysis,
  - API/data-flow tracing.
- [ ] `USE-TEST-001` Add integration tests to ensure new docs/examples remain aligned with live tool contract fields.
- [ ] `USE-ADR-002` Add/update ADR if CI guidance or preset strategy introduces policy-level defaults.

## Later

- [ ] `DX-001` Add maintainership automation for changelog/release notes.
- [ ] `DX-002` Add issue labels/triage docs for single-maintainer workflow.

## Icebox

- [ ] `ENH-TS-001` Optional enhanced parsing path for TS/JS (only with explicit dependency and ADR approval).
- [ ] `ENH-JAVA-001` Optional enhanced parsing path for Java (same gating).
- [ ] `ENH-OTHERS-001` Optional enhanced parsing path for Go/Rust/C++/C# (same gating).

## Execution Sequence (recommended)

1. `USE-DEC-001`, `USE-DEC-002`, `USE-DEC-003`
2. `USE-SPEC-001`, `USE-ADR-001`
3. `USE-QA-001`, `USE-OBS-001`
4. `USE-DOC-001`
5. `USE-PERF-001`, `USE-CI-001`
6. `USE-DOC-002`, `USE-TEST-001`
7. `USE-ADR-002` (only if needed by final design choices)

## Notes

- Any schema/contract changes require `SPEC.md` update first.
- Any architectural or policy-level decision requires ADR update/addition.
- Keep all outputs deterministic and bounded.
