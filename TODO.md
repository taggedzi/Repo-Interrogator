# TODO

This file is the active roadmap index.

For historical detail, see:
- `docs/roadmap/archive-2026-02-09-implementation-plan.md`

## How to use this file

- Keep items short (one line each).
- Keep this file as the primary task tracker (no GitHub issue dependency).
- Put behavior contracts in `SPEC.md`.
- Put design decisions in `docs/adr/`.
- Move completed items from `Now`/`Next` to `Done (recent)`.

## Working workflow with Codex

1. Add or update an item ID in `Now`/`Next` (example: `V2.5-REF-003`).
2. Ask Codex: `Implement V2.5-REF-003 from TODO.md`.
3. Codex implements only that scoped item, runs quality gates, and reports results.
4. Mark the item complete and move it to `Done (recent)` when accepted.
5. If scope changes tool schemas or determinism guarantees, update `SPEC.md` and ADRs first.

## Now

- [x] `V2.5-REF-001` Define deterministic cross-file reference contract in `SPEC.md` (fields, ordering, limits).
- [x] `V2.5-REF-002` Add ADR for cross-file references scope and non-goals.
- [x] `V2.5-REF-003` Implement Python reference extraction (definition -> usage links, deterministic ordering).
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
- [x] `V2.5-REF-001` Added cross-file references contract to `SPEC.md` (including deterministic ordering and limits).
- [x] `V2.5-REF-002` Added ADR-0013 for v2.5 deterministic cross-file references scope/non-goals.
- [x] `V2.5-REF-003` Added Python AST-based symbol usage extraction with deterministic reference linking and ordering.
- [x] `DOC-001` Added/updated contributor and security/community templates (`CONTRIBUTING.md`, `SECURITY.md`, issue/PR templates).
- [x] `DOC-002` Updated `docs/USAGE.md` and `docs/AI_INTEGRATION.md` for v2 outline fields/semantics.

## Notes

- If an item changes tool schemas or determinism guarantees, create/update ADR first.
- For major scope changes, add a brief milestone section in `SPEC.md`.

## V2.5 Detailed Entries

### `V2.5-REF-001` Deterministic cross-file reference contract in SPEC

**Goal**
- Define what a “reference” means for this project and make output contract deterministic.

**Required changes**
- Update `SPEC.md` with reference semantics:
  - definition-to-usage linkage model,
  - deterministic ordering rules,
  - confidence/strategy fields (`ast` vs lexical fallback),
  - strict output limits and truncation signaling.
- Define whether references are returned by a new tool (`repo.references`) or by extending existing payloads.

**Tests to add/update**
- Add schema/contract tests for reference payload shape and stable ordering.

**Acceptance criteria**
- Contract is explicit, testable, and cross-language compatible.
- No runtime execution or nondeterministic ranking introduced.

### `V2.5-REF-002` ADR for cross-file references

**Goal**
- Record scope, rationale, and non-goals for reference linking.

**Required changes**
- Add ADR in `docs/adr/` covering:
  - deterministic-only approach,
  - Python-first depth and lexical fallback scope,
  - known false-positive/false-negative tradeoffs,
  - rollout and revisit triggers.

**Tests to add/update**
- None (documentation/decision artifact).

**Acceptance criteria**
- ADR accepted and aligned with `SPEC.md`.

### `V2.5-REF-003` Python references (AST-based)

**Goal**
- Provide useful cross-file references for Python symbols with deterministic behavior.

**Required changes**
- Implement AST-based symbol usage extraction for Python files.
- Link references to known declarations (best effort) across indexed Python files.
- Return stable fields such as:
  - symbol name,
  - path,
  - line,
  - reference kind,
  - strategy/confidence.
- Enforce deterministic sort and output caps.

**Tests to add/update**
- Unit tests for:
  - imports,
  - direct calls,
  - attribute calls,
  - ambiguous/unresolved symbols.
- Integration tests for cross-file definition/usage linking on fixtures.

**Acceptance criteria**
- Repeated runs on same repo state return identical reference payloads.
- Output is useful for impact analysis and safe under limits.

### `V2.5-RANK-001` Deterministic ranking boost

**Goal**
- Improve context bundle relevance using deterministic structural signals.

**Required changes**
- Add deterministic ranking signals for bundle selection:
  - symbol-definition match,
  - reference proximity (definition + usage),
  - path/name relevance,
  - stable tie-break rules.
- Keep all ranking deterministic and auditable.

**Tests to add/update**
- Ranking stability tests with fixed prompts/fixtures.
- Tie-break tests to ensure explicit order invariants.

**Acceptance criteria**
- Bundle relevance improves on fixture prompts without introducing nondeterminism.
- Tie-breaks are explicit and stable.

### `V2.5-RANK-002` `why_selected` explanations

**Goal**
- Make bundle selection explainable for humans and AI consumers.

**Required changes**
- Emit `why_selected` per bundle selection with compact deterministic rationale:
  - matched signal(s),
  - score components,
  - source query/symbol reference.
- Keep explanation content bounded and stable.

**Tests to add/update**
- Tests asserting `why_selected` exists and includes expected rationale keys.
- Snapshot tests for explanation stability.

**Acceptance criteria**
- Every selected excerpt has self-describing deterministic rationale.
- Explanations are useful for debugging retrieval quality.

### `V2.5-REF-004` Lexical reference fallback for non-Python languages

**Goal**
- Provide best-effort cross-file references for TS/JS/Java/Go/Rust/C++/C# without changing parser strategy.

**Required changes**
- Implement lexical reference extraction fallback for non-Python adapters.
- Keep behavior conservative and deterministic:
  - prefer precision over aggressive matching,
  - explicit confidence/strategy metadata,
  - deterministic ordering and limits.

**Tests to add/update**
- Per-language fixture tests for common reference forms.
- Cross-language determinism tests for repeated runs and path normalization.

**Acceptance criteria**
- Non-Python references are available and deterministic.
- False positives are bounded and documented.

### `V2.5-TEST-001` Golden and regression coverage

**Goal**
- Lock v2.5 behavior with repeatable regression tests.

**Required changes**
- Add/update golden fixtures for:
  - Python references,
  - non-Python lexical references,
  - bundle ranking outputs with `why_selected`.
- Add cross-platform/path-style stability checks for reference outputs.

**Tests to add/update**
- Unit/integration tests for schema, ordering, limits, and stability.

**Acceptance criteria**
- Test suite catches ordering/schema regressions reliably.
- Full quality gates pass with updated fixtures.
