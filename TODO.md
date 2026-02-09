# Repo-Interrogator Implementation TODO (Prompt-Driven)

## 1) Project stance summary

Repo-Interrogator is a local-first, deterministic MCP server over STDIO for interrogating exactly one repository per server instance.  
It is integration-first for AI clients, passive and interrogative (not agentic), with strong sandboxing, auditable outputs, and no LLM calls in v1.

## 2) Global Rules For Every Step

- Follow `SPEC.md` as source of truth; ADRs are binding architectural intent.
- Deterministic behavior only; no LLM calls, no nondeterministic ordering.
- MCP transport is STDIO only in v1; no HTTP/SSE additions.
- Enforce single-repo scope (`repo_root`) for all operations.
- Enforce deny-by-default file access and block-over-redact policy.
- Keep core language-agnostic; Python-specific logic only in adapter layer.
- Do not add runtime dependencies without explicit human approval.
- Use Ruff only for formatting/linting; do not add or reintroduce Black.
- Use user-managed `.venv`; do not create/modify/delete virtual environments.
- Tests must be deterministic, self-contained, no network calls.
- Keep output schemas stable and explicit; tool contracts are API contracts.

## 3) Definition of Done For Each Step

Run these gates and record results in the step report:

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

If a step is very early scaffolding and one or more gates are not yet runnable, the step is **not done**; finish missing scaffolding in that same step until all four gates execute.

## 4) Prompt Template

Use this exact structure for every implementation step:

```text
Implement Step <N> only from TODO.md.

Goal:
- <one-paragraph goal copied from TODO.md>

Scope:
- Only make changes listed in Step <N>.
- Do not start later steps.

Required changes:
- <bullet list copied from TODO.md step>

Tests to add/update:
- <bullet list copied from TODO.md step>

Command gates:
- python -m ruff format .
- python -m ruff check .
- python -m mypy src
- python -m pytest -q

Report back with:
- Files changed
- Tests added/updated
- Command output summary
- Determinism/sandboxing notes
- Proposed commit message (single line)
```

## 5) Decision Gates (STOP and ask human before proceeding)

1. **Index storage format + schema versioning**
   - Decide on on-disk format and explicit version migration policy before implementing persistent index internals.
2. **Context bundle schema + artifact persistence**
   - Decide canonical JSON schema and whether to write `last_bundle` artifacts by default, and exact storage path.
3. **Default limits and raise policy**
   - Decide defaults for max file size, max lines, max response bytes, max bundle size, and whether repo config may raise hard ceilings.
4. **Denylist override policy**
   - Decide whether repo-level config can relax denylist entries; strict default remains mandatory.
5. **Pre-commit vs CI-only**
   - Decide whether to add optional `pre-commit` hooks or keep enforcement CI-only.
6. **BM25 dependency escape hatch**
   - If stdlib BM25 is insufficient, STOP and request dependency approval with license, maintenance, and security rationale.

---

## 6) Step-by-step plan aligned to SPEC.md milestones

## M0 - MCP server + sandbox + logging

### Step 1 - Bootstrap package and repo skeleton (A)

**Goal**  
Create production-ready baseline structure and packaging so all tooling gates run and future slices remain small.

**Required changes**
- Add `src/repo_mcp/` package skeleton aligned to expected modules:
  - `server.py`, `tools/`, `index/`, `adapters/`, `bundler/`, `security/`, `logging/`.
- Add `pyproject.toml` with:
  - build backend, package metadata, Python `>=3.11`,
  - Ruff config, mypy config (`src`), pytest config.
- Add package `__init__.py` files and minimal typed module stubs.
- Add MCP server entrypoint `repo_mcp.server:main` and optional `console_scripts` hook.
- Add minimal docs stubs: `README.md`, `SECURITY.md`, `examples/repo_mcp.toml`.

**Tests to add/update**
- `tests/test_smoke_imports.py` for package import and entrypoint callable.
- `tests/test_project_layout.py` asserting required package paths exist.

**Acceptance criteria**
- `pip`-installable package metadata is valid.
- Entry module exists and can be imported without side effects.
- Docs stubs exist and do not contradict `SPEC.md`/ADRs.

**Prompt**
```text
Implement Step 1 only from TODO.md.
```

### Step 2 - MCP protocol skeleton and tool registry (B, partial G)

**Goal**  
Implement STDIO request/response backbone with stable envelope and deterministic tool dispatch.

**Required changes**
- Implement JSON-RPC/MCP STDIO loop with request parsing and response writing.
- Add common envelope fields: `request_id`, `ok`, `result`, `warnings`, `blocked`.
- Add deterministic tool registry and router with explicit unknown-tool errors.
- Define schema validation layer (manual/typed) with explicit error codes.
- Stub tools: `repo.status`, `repo.list_files`, `repo.open_file`, `repo.search`, `repo.refresh_index`, `repo.audit_log`.

**Tests to add/update**
- `tests/integration/test_stdio_server_smoke.py` for request routing and envelope shape.
- `tests/unit/test_tool_registry.py` for deterministic registration/dispatch order.
- `tests/unit/test_error_envelope.py` for malformed request and unknown tool behavior.

**Acceptance criteria**
- Server handles multiple sequential requests over STDIO.
- Every response includes `request_id`.
- Errors are explicit, structured, and non-ambiguous.

**Prompt**
```text
Implement Step 2 only from TODO.md.
```

### Step 3 - Sandboxing core path policy (C)

**Goal**  
Implement hard repo boundary checks and secure path resolution primitives used by all file-reading tools.

**Required changes**
- Add canonical path resolver scoped to `repo_root`.
- Block traversal (`..`), absolute paths outside root, and symlink escapes.
- Normalize Windows/WSL/POSIX paths deterministically.
- Return explicit blocked reason metadata (no content leakage).

**Tests to add/update**
- `tests/unit/security/test_path_traversal_blocked.py`
- `tests/unit/security/test_symlink_escape_blocked.py`
- `tests/unit/security/test_absolute_outside_root_blocked.py`
- `tests/unit/security/test_path_normalization_cross_platform.py`

**Acceptance criteria**
- All escape attempts are blocked with explicit reason.
- No blocked response includes partial file content.
- Path ordering/normalization is stable across platforms.

**Prompt**
```text
Implement Step 3 only from TODO.md.
```

### Step 4 - Denylist and limits enforcement (C, J partial)

**Goal**  
Enforce deny-by-default sensitive file policy and hard read limits in shared security layer.

**Required changes**
- Implement denylist matcher for patterns in `SPEC.md`.
- Add max file bytes and max open-line limits enforcement.
- Add max total response bytes and max search hits limit guards.
- Wire blocked responses with remediation hints.
- Ensure block-over-redact default behavior.

**Tests to add/update**
- `tests/unit/security/test_denylist_patterns.py`
- `tests/unit/security/test_limit_enforcement.py`
- `tests/unit/security/test_block_not_redact_policy.py`

**Acceptance criteria**
- Sensitive files are blocked by default.
- Oversized content is blocked deterministically.
- Limit behavior is stable and documented in test fixtures.

**Prompt**
```text
Implement Step 4 only from TODO.md.
```

### Step 5 - Structured JSONL audit logging (D, partial G)

**Goal**  
Add auditable, sanitized request logging with strict no-secret/no-content leakage rules.

**Required changes**
- Implement JSONL audit logger with request lifecycle events.
- Log `request_id`, tool name, timestamps, and safe metadata only.
- Add `repo.audit_log` tool for sanitized retrieval (`since`, `limit`).
- Enforce explicit exclusions for env values, credentials, full file contents.

**Tests to add/update**
- `tests/unit/logging/test_audit_log_schema.py`
- `tests/unit/logging/test_audit_log_sanitization.py`
- `tests/integration/test_repo_audit_log_tool.py`

**Acceptance criteria**
- Audit entries are valid JSONL and human-inspectable.
- Sensitive fields are never present.
- `repo.audit_log` returns bounded, sanitized records.

**Prompt**
```text
Implement Step 5 only from TODO.md.
```

## M1 - Index + BM25 search

### Step 6 - Config system and merge order (J)

**Goal**  
Introduce deterministic config loading with explicit precedence and typed limits/index settings.

**Required changes**
- Add default config model with limits/index/adapter toggles.
- Load optional `repo_mcp.toml` from `repo_root`.
- Merge order: defaults -> repo config -> startup/CLI flags.
- Surface effective config in `repo.status`.

**Tests to add/update**
- `tests/unit/config/test_merge_order.py`
- `tests/unit/config/test_invalid_config_errors.py`
- `tests/integration/test_repo_status_config_snapshot.py`

**Acceptance criteria**
- Effective config is deterministic and reproducible.
- Invalid config fails explicitly and safely.
- `repo.status` reports active limits/adapters.

**Prompt**
```text
Implement Step 6 only from TODO.md.
```

### Step 7 - Deterministic file discovery and refresh bookkeeping (E)

**Goal**  
Implement deterministic indexed file discovery and incremental change tracking scaffolding.

**Required changes**
- Discover text-like files per `SPEC.md` extensions and ignore rules.
- Exclude binary-like files deterministically.
- Track per-file metadata (`mtime`, hash, size) for incremental refresh.
- Implement deleted-file removal bookkeeping.

**Tests to add/update**
- `tests/unit/index/test_file_discovery_rules.py`
- `tests/unit/index/test_incremental_change_detection.py`
- `tests/unit/index/test_deleted_file_removal.py`

**Acceptance criteria**
- Discovery output ordering is explicit and stable.
- Changed/unchanged/deleted classification is deterministic.
- Ignore/config behavior is covered by fixtures.

**Prompt**
```text
Implement Step 7 only from TODO.md.
```

### Step 8 - Deterministic chunking and stable chunk IDs (E)

**Goal**  
Add line-based chunking with stable identifiers and overlap policy from `SPEC.md`.

**Required changes**
- Implement default chunking (200 lines, 30 overlap).
- Generate stable `chunk_id` derived from deterministic inputs.
- Store chunk metadata: path, start_line, end_line, chunk_id.
- Expose indexed chunk stats in `repo.status` or refresh result.

**Tests to add/update**
- `tests/unit/index/test_chunk_boundaries.py`
- `tests/unit/index/test_chunk_id_stability.py`
- `tests/unit/index/test_chunk_ordering.py`

**Acceptance criteria**
- Same repo state always yields same chunk sequence/IDs.
- Overlap/boundary rules are exact and tested.
- Chunk metadata is complete and self-describing.

**Prompt**
```text
Implement Step 8 only from TODO.md.
```

### Step 9 - STOP: index persistence format decision gate

**Goal**  
Lock index storage format and schema-version strategy before persistent storage implementation.

**Required changes**
- Do not implement code in this step.
- Record chosen format/version policy in a new ADR if needed.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Human-approved decision captured in writing.
- Follow-up implementation constraints are clear.

**Prompt**
```text
Implement Step 9 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 10 without explicit approval.
```

### Step 10 - Index persistence + `repo.refresh_index` tool (E, G)

**Goal**  
Implement persistent incremental index refresh and tool response contract.

**Required changes**
- Persist index metadata/chunks using approved format + schema version.
- Implement `repo.refresh_index(force?)` with added/updated/removed counts.
- Return duration and refresh timestamp deterministically.
- Ensure stale/deleted entries are removed atomically.

**Tests to add/update**
- `tests/integration/test_refresh_index_roundtrip.py`
- `tests/unit/index/test_index_schema_versioning.py`
- `tests/unit/index/test_force_refresh_behavior.py`

**Acceptance criteria**
- Refresh is incremental by default and forceable.
- Returned counts and timestamp fields are correct.
- Storage schema is versioned and validated.

**Prompt**
```text
Implement Step 10 only from TODO.md.
```

### Step 11 - BM25 search core + stable ranking (F, G)

**Goal**  
Implement deterministic BM25 search with strict tie-breaking and bounded outputs.

**Required changes**
- Build stdlib-first BM25 scorer over indexed chunks.
- Add query tokenization with deterministic normalization.
- Implement tie-break ordering (score desc, path asc, line asc).
- Implement filters: `file_glob`, path constraints, `top_k`.
- Implement `repo.search` tool response schema with matched terms/snippets.

**Tests to add/update**
- `tests/unit/search/test_bm25_basic.py`
- `tests/unit/search/test_tie_break_stability.py`
- `tests/unit/search/test_filters_and_limits.py`
- `tests/integration/test_repo_search_tool.py`

**Acceptance criteria**
- Same inputs always return same ranked results.
- Tie-breaks are explicit and tested.
- Search obeys global size/hit limits.

**Prompt**
```text
Implement Step 11 only from TODO.md.
```

## M2 - Python adapter + outline

### Step 12 - Adapter plugin architecture and fallback adapter (H)

**Goal**  
Introduce pluggable adapter interfaces and deterministic adapter selection.

**Required changes**
- Define adapter protocol: `supports_path`, `outline`, optional `smart_chunks`, optional `symbol_hints`.
- Implement adapter registry and selection order.
- Implement default lexical fallback adapter for non-Python files.

**Tests to add/update**
- `tests/unit/adapters/test_registry_selection.py`
- `tests/unit/adapters/test_fallback_adapter.py`

**Acceptance criteria**
- Core logic calls adapters via interface only.
- Non-Python paths resolve to lexical fallback deterministically.

**Prompt**
```text
Implement Step 12 only from TODO.md.
```

### Step 13 - Python AST outline + `repo.outline` tool (H, G)

**Goal**  
Add Python-first structural outline extraction with stable symbol metadata.

**Required changes**
- Implement Python adapter using `ast`.
- Extract functions/classes/methods with signatures and line ranges.
- Include first docstring line optionally.
- Implement `repo.outline` tool with language and symbol list.

**Tests to add/update**
- `tests/unit/adapters/test_python_outline_symbols.py`
- `tests/unit/adapters/test_python_outline_signatures.py`
- `tests/integration/test_repo_outline_tool.py`

**Acceptance criteria**
- Outline output is deterministic and sorted.
- Symbol ranges/signatures are correct for fixture files.
- Non-Python files return lexical/fallback behavior.

**Prompt**
```text
Implement Step 13 only from TODO.md.
```

## M3 - Deterministic context bundler

### Step 14 - STOP: bundle schema + artifact persistence decision gate

**Goal**  
Finalize context bundle JSON schema and artifact persistence policy before implementation.

**Required changes**
- Do not implement code in this step.
- Capture schema and `last_bundle` storage decision (including path and defaults).

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Human-approved schema and persistence policy documented.

**Prompt**
```text
Implement Step 14 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 15 without explicit approval.
```

### Step 15 - Deterministic bundling engine with budgets (I)

**Goal**  
Implement deterministic context selection pipeline with strict budget enforcement.

**Required changes**
- Add keyword extraction from prompt (deterministic heuristic).
- Run multi-query search passes (prompt + keywords), rank and dedupe.
- Prefer symbol-aligned ranges for Python files when available.
- Enforce budgets: `max_files`, `max_total_lines` (and configured byte bounds).
- Emit `bundle_id`, prompt fingerprint, selections, rationale, citations.

**Tests to add/update**
- `tests/unit/bundler/test_budget_enforcement.py`
- `tests/unit/bundler/test_dedupe_and_rank_stability.py`
- `tests/unit/bundler/test_citation_completeness.py`

**Acceptance criteria**
- Bundle output is deterministic for fixed repo/prompt.
- Budgets are strict with explicit truncation signaling.
- Every excerpt has path+line citation and rationale.

**Prompt**
```text
Implement Step 15 only from TODO.md.
```

### Step 16 - `repo.build_context_bundle` tool + optional exports (I, G)

**Goal**  
Expose bundle engine through MCP tool contract and optional human-readable artifacts.

**Required changes**
- Implement `repo.build_context_bundle` input/output schema per `SPEC.md`.
- Wire optional `last_bundle.json` and `last_bundle.md` export behavior per approved decision.
- Add audit events for bundle creation without leaking file contents.

**Tests to add/update**
- `tests/integration/test_repo_build_context_bundle_tool.py`
- `tests/unit/bundler/test_bundle_export_policy.py`
- `tests/unit/logging/test_bundle_audit_sanitization.py`

**Acceptance criteria**
- Tool returns fully structured bundle payload with citations/rationale.
- Export behavior matches explicit policy and stays bounded.
- Audit log remains sanitized.

**Prompt**
```text
Implement Step 16 only from TODO.md.
```

## M4 - Plugin + future-ready hooks + release capability

### Step 17 - Complete core tool set behavior hardening (G)

**Goal**  
Harden and finalize required v1 tools and schema conformance across all success/error paths.

**Required changes**
- Finalize `repo.status`, `repo.list_files`, `repo.open_file`, `repo.search`, `repo.refresh_index`, `repo.audit_log`, `repo.outline`, `repo.build_context_bundle`.
- Add consistent warnings and blocked-response semantics.
- Ensure all tool outputs are self-describing and deterministic.

**Tests to add/update**
- `tests/integration/test_tool_contract_matrix.py`
- `tests/unit/tools/test_blocked_response_shapes.py`
- `tests/unit/tools/test_ordering_determinism.py`

**Acceptance criteria**
- Tool contracts are stable and validated by integration matrix tests.
- Blocked/error responses never leak restricted content.

**Prompt**
```text
Implement Step 17 only from TODO.md.
```

### Step 18 - STOP: limits policy + denylist override decision gate

**Goal**  
Freeze security-sensitive policy on configurable limits and denylist relaxation.

**Required changes**
- Do not implement code in this step.
- Resolve:
  - default limits,
  - whether repo config can raise ceilings,
  - whether repo config can relax denylist.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Human-approved policy documented before policy wiring.

**Prompt**
```text
Implement Step 18 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 19 without explicit approval.
```

### Step 19 - Policy wiring for limits/denylist and docs alignment (C, J)

**Goal**  
Implement final approved policy for limits and denylist behavior and align docs/examples.

**Required changes**
- Wire approved ceilings and override behavior into config/security layers.
- Update `README.md`, `SECURITY.md`, and `examples/repo_mcp.toml`.
- Ensure strict defaults remain safe-by-default.

**Tests to add/update**
- `tests/unit/config/test_limit_override_policy.py`
- `tests/unit/security/test_denylist_override_policy.py`
- `tests/integration/test_policy_effective_behavior.py`

**Acceptance criteria**
- Runtime behavior matches approved policy exactly.
- Documentation and examples are accurate and consistent.

**Prompt**
```text
Implement Step 19 only from TODO.md.
```

### Step 20 - End-to-end integration tests over STDIO (K)

**Goal**  
Add full deterministic integration suite that exercises primary agent workflow over STDIO transport.

**Required changes**
- Add integration harness to run server subprocess over STDIO.
- Test sequence: status -> refresh -> list/open/search/outline -> bundle -> audit.
- Add fixtures ensuring deterministic, self-contained behavior.

**Tests to add/update**
- `tests/integration/test_stdio_workflow_e2e.py`
- `tests/integration/test_no_network_assumption.py`

**Acceptance criteria**
- E2E workflow passes with deterministic outputs on repeated runs.
- No test uses network resources.

**Prompt**
```text
Implement Step 20 only from TODO.md.
```

### Step 21 - Cross-platform determinism and normalization suite (K)

**Goal**  
Guarantee Windows/WSL/POSIX path and ordering consistency in security, index, and tool outputs.

**Required changes**
- Add cross-platform path normalization helpers where missing.
- Add fixtures with mixed path styles and casing edge cases.
- Validate deterministic ordering independent of filesystem enumeration order.

**Tests to add/update**
- `tests/unit/platform/test_windows_posix_normalization.py`
- `tests/integration/test_cross_platform_output_stability.py`

**Acceptance criteria**
- Outputs are normalized and stable across platform-specific path inputs.
- Determinism tests fail on ordering regressions.

**Prompt**
```text
Implement Step 21 only from TODO.md.
```

### Step 22 - CI pipeline for lint/type/test/build/install smoke (L)

**Goal**  
Make repository release-capable with automated quality gates and build verification.

**Required changes**
- Add GitHub Actions workflow for push/PR:
  - setup Python,
  - run Ruff format check strategy,
  - Ruff lint, mypy, pytest,
  - build sdist/wheel,
  - install artifact smoke test.
- Ensure workflow is deterministic and does not require network beyond dependency install.

**Tests to add/update**
- CI workflow validation via local dry-run checks where feasible.
- Optional `tests/packaging/test_entrypoint_import.py` smoke assertion.

**Acceptance criteria**
- CI fails on any lint/type/test/build regression.
- Built artifacts install and import successfully.

**Prompt**
```text
Implement Step 22 only from TODO.md.
```

### Step 23 - STOP: pre-commit vs CI-only decision gate

**Goal**  
Decide developer workflow enforcement scope before adding local hooks.

**Required changes**
- Do not implement code in this step.
- Obtain explicit decision: add optional `pre-commit` config or keep CI-only.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Decision documented and approved.

**Prompt**
```text
Implement Step 23 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 24 without explicit approval.
```

### Step 24 - Release automation (GitHub Release artifacts, optional publish) (L)

**Goal**  
Add tag-driven release workflow that produces auditable artifacts and optional guarded publish.

**Required changes**
- Add release workflow triggered by version tags.
- Build and attach sdist/wheel to GitHub Release.
- Add optional, explicitly guarded publish step (disabled by default unless secrets + flag present).
- Document release process in `README.md` or `docs/release.md`.

**Tests to add/update**
- Workflow assertions for tag trigger and artifact paths.
- Packaging smoke check in release workflow.

**Acceptance criteria**
- Tag push creates release artifacts automatically.
- Publish remains opt-in and guarded.
- Release process is documented and reproducible.

**Prompt**
```text
Implement Step 24 only from TODO.md.
```

---

## 7) Completion checklist for production-ready, release-capable status

- All steps completed in order, including STOP decision gates.
- All mandatory capabilities A-L implemented and tested.
- All tool contracts stable and documented.
- Determinism/security invariants validated by unit + integration suites.
- CI and release workflows operational with reproducible artifacts.

---

## 8) Language Adapter Expansion Track (TS/JS/Java/Go/Rust/C++/C#)

### Overview

This expansion track adds multi-language outline support through the existing plugin adapter system without changing core transport, sandboxing, or deterministic guarantees.

- Keep MCP transport STDIO-only.
- Keep server passive and interrogative (no LLM usage).
- Keep security and path policy in core; adapters must never bypass policy.
- Keep deterministic ordering and stable output schemas.
- Start with zero new runtime dependencies using lexical outlines for all target languages.
- Treat enhanced parser-based approaches as optional follow-on work behind explicit decision gates.

### Prerequisites

- Baseline TODO steps through Step 24 are complete and passing.
- Adapter registry and fallback behavior from Steps 12-13 are stable.
- `repo.outline` and bundler integration behavior from Steps 13, 16, and 17 are stable.

### Adapter interface expectations (applies to every new adapter)

- `supports_path(path: str) -> bool`:
  - deterministic extension-based detection only.
- `outline(path: str, content: str) -> OutlineResult`:
  - stable schema and deterministic ordering.
  - output symbols must include: `name`, `kind`, `start_line`, `end_line`.
  - include `signature` when feasible and deterministic.
- Optional `chunking_hints(...)` (if enabled later):
  - must be deterministic and additive; core chunker remains authoritative.
- Deterministic ordering rules:
  - sort by `start_line`, then `end_line`, then `name`, then `kind`.
  - no dependence on hash iteration or platform file ordering.
- Stable schema rules:
  - language identifier is explicit.
  - missing data must be explicit (`null`/empty), never inferred nondeterministically.

### Language detection and outline strategy matrix

- TypeScript
  - Extensions: `.ts`, `.tsx`, `.mts`, `.cts`.
  - Lexical first: classes, interfaces, enums, type aliases, functions, exported const/let/var, methods.
  - Enhanced option (gated): TypeScript compiler API, tree-sitter, or lightweight parser.
  - Edge cases: decorators, overload signatures, namespace merges, JSX/TSX ambiguity.
- JavaScript
  - Extensions: `.js`, `.jsx`, `.mjs`, `.cjs`.
  - Lexical first: function declarations, class declarations, methods, exports (`export`, `module.exports`, `exports.*`).
  - Enhanced option (gated): tree-sitter or parser package.
  - Edge cases: dynamic exports, prototype assignments, class fields.
- Java
  - Extensions: `.java`.
  - Lexical first: package/import, classes/interfaces/enums/records, methods, constructors.
  - Enhanced option (gated): `javalang` or tree-sitter.
  - Edge cases: nested/anonymous classes, annotations, generics and bounds.
- Go
  - Extensions: `.go`.
  - Lexical first: package, type declarations, funcs/methods (receiver forms), const/var groups.
  - Enhanced option (gated): external `go` toolchain parsing.
  - Edge cases: grouped declarations, receiver syntax variants, build tags.
- Rust
  - Extensions: `.rs`.
  - Lexical first: `mod`, `struct`, `enum`, `trait`, `impl`, `fn`, `const`, `type`.
  - Enhanced option (gated): tree-sitter or external tooling.
  - Edge cases: macro-generated items, impl blocks with where clauses, trait impl methods.
- C++
  - Extensions: `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx`, `.h`.
  - Lexical first: namespaces, classes/structs/enums, free functions, methods where recognizable.
  - Enhanced option (gated): tree-sitter or libclang-based approach.
  - Edge cases: templates, macros, function pointer syntax, declarations vs definitions.
- C#
  - Extensions: `.cs`.
  - Lexical first: namespaces, classes/structs/interfaces/enums/records, methods/properties/events.
  - Enhanced option (gated): tree-sitter or Roslyn-based external tooling.
  - Edge cases: partial classes, attributes, expression-bodied members, top-level statements.

### Expansion-specific Decision Gates (STOP and ask human before proceeding)

1. **Tree-sitter adoption for multi-language parsing**
   - Pros: broad language coverage, better structural accuracy.
   - Cons: dependency/runtime portability burden, parser version management, fixture drift risk.
2. **Optional external toolchain integration**
   - Consider `go`, `javac`, `clang`, `rustc`, or similar.
   - Default should remain no external executables to preserve hermetic deterministic behavior.
3. **Outline-only vs language-aware chunking hints**
   - Decide whether lexical/parsing improvements should remain outline-only or also influence chunk selection.

## M5 - Multi-language lexical adapter baseline (zero new runtime deps)

### Step 25 - Adapter contract hardening for multi-language support

**Goal**  
Finalize adapter contract semantics and shared deterministic ordering helpers before adding new language adapters.

**Required changes**
- Codify adapter output schema invariants shared by all adapters.
- Add reusable symbol sorting helper and signature normalization utility.
- Document optional `chunking_hints` as not required for baseline.

**Tests to add/update**
- `tests/unit/adapters/test_adapter_contract_invariants.py`
- `tests/unit/adapters/test_symbol_ordering_rules.py`

**Acceptance criteria**
- All adapters conform to the same symbol schema and ordering rules.
- Contract tests fail on missing required symbol fields.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 25 only from TODO.md.
```

### Step 26 - Shared lexical outline utilities

**Goal**  
Create deterministic lexical scanning utilities reusable by all new language adapters.

**Required changes**
- Add shared token/comment/string skipping helpers.
- Add brace and block tracking utilities with deterministic line accounting.
- Add safe fallback behavior for malformed source.

**Tests to add/update**
- `tests/unit/adapters/test_lexical_scanner_basics.py`
- `tests/unit/adapters/test_lexical_scanner_edge_cases.py`

**Acceptance criteria**
- Scanner behavior is deterministic and independent of platform.
- Utilities never execute external tools or parse via network calls.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 26 only from TODO.md.
```

### Step 27 - TypeScript and JavaScript lexical adapters

**Goal**  
Add deterministic lexical outline adapters for TS/JS with export-aware symbol extraction.

**Required changes**
- Add extension detection for TS/JS families.
- Extract top-level symbols: classes, interfaces, enums, type aliases, functions, exported bindings, methods where deterministic.
- Populate stable ranges and signatures where feasible.
- Register adapters in plugin registry without changing core server behavior.

**Tests to add/update**
- `tests/unit/adapters/test_ts_outline_lexical.py`
- `tests/unit/adapters/test_js_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/ts_js/`.

**Acceptance criteria**
- TS/JS files select the correct adapter deterministically.
- Output symbol ordering and ranges are stable across repeated runs.
- Unknown or ambiguous constructs degrade to safe minimal symbols, not errors.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 27 only from TODO.md.
```

### Step 28 - Java lexical adapter

**Goal**  
Add deterministic lexical outline adapter for Java source.

**Required changes**
- Detect `.java` files.
- Extract package-aware top-level symbols: classes/interfaces/enums/records and methods/constructors.
- Emit stable ranges and signatures where feasible.
- Document unsupported constructs in adapter docstring/tests.

**Tests to add/update**
- `tests/unit/adapters/test_java_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/java/`.

**Acceptance criteria**
- Java outlines are deterministic and schema-compliant.
- Nested/anonymous complexity does not break output stability.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 28 only from TODO.md.
```

### Step 29 - Go lexical adapter

**Goal**  
Add deterministic lexical outline adapter for Go without invoking external toolchains.

**Required changes**
- Detect `.go` files.
- Extract package-level symbols: types, funcs, methods, const/var blocks.
- Handle receiver signatures lexically where deterministic.
- Explicitly avoid `go` executable usage in baseline.

**Tests to add/update**
- `tests/unit/adapters/test_go_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/go/`.

**Acceptance criteria**
- Go outlines are deterministic with stable ranges.
- Adapter never shells out to `go` or external binaries.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 29 only from TODO.md.
```

### Step 30 - Rust lexical adapter

**Goal**  
Add deterministic lexical outline adapter for Rust.

**Required changes**
- Detect `.rs` files.
- Extract symbols: `mod`, `struct`, `enum`, `trait`, `impl`, `fn`, `const`, `type`.
- Represent impl methods with stable naming convention where feasible.
- Document macro-related limitations.

**Tests to add/update**
- `tests/unit/adapters/test_rust_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/rust/`.

**Acceptance criteria**
- Rust outline is deterministic for fixed input.
- Macro-heavy files degrade gracefully with explicit limitations.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 30 only from TODO.md.
```

### Step 31 - C++ lexical adapter

**Goal**  
Add deterministic lexical outline adapter for C++/headers.

**Required changes**
- Detect canonical C/C++ extensions in scope.
- Extract namespaces, classes/structs/enums, and functions/methods where deterministic.
- Handle declaration/definition ambiguity with conservative symbol emission.
- Document template/macro limitations explicitly.

**Tests to add/update**
- `tests/unit/adapters/test_cpp_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/cpp/`.

**Acceptance criteria**
- C++ outline output remains stable even on partially ambiguous syntax.
- Adapter avoids heuristic randomness and external tooling.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 31 only from TODO.md.
```

### Step 32 - C# lexical adapter

**Goal**  
Add deterministic lexical outline adapter for C#.

**Required changes**
- Detect `.cs` files.
- Extract symbols: namespaces, classes/structs/interfaces/enums/records, methods/properties/events when feasible.
- Include stable signature fragments for methods and constructors.
- Document partial class and attribute limitations.

**Tests to add/update**
- `tests/unit/adapters/test_csharp_outline_lexical.py`
- Golden fixtures under `tests/fixtures/adapters/csharp/`.

**Acceptance criteria**
- C# outlines are deterministic with stable ordering and ranges.
- Unsupported syntax is handled conservatively, not with speculative parsing.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 32 only from TODO.md.
```

### Step 33 - Adapter selection integration and `repo.outline` coverage

**Goal**  
Ensure `repo.outline` consistently selects the new adapters and falls back cleanly.

**Required changes**
- Update registry wiring and deterministic selection precedence.
- Ensure unsupported files still use fallback adapter.
- Add integration checks for all supported language extensions.

**Tests to add/update**
- `tests/integration/test_repo_outline_multilanguage_selection.py`
- `tests/unit/adapters/test_registry_selection_multilanguage.py`

**Acceptance criteria**
- `repo.outline` picks expected adapter by path extension.
- Fallback behavior remains deterministic and unchanged for unknown types.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 33 only from TODO.md.
```

### Step 34 - Context bundler integration with non-Python outlines

**Goal**  
Ensure bundler uses outline metadata when available for any adapter, with deterministic fallback.

**Required changes**
- Generalize bundler outline consumption to adapter-agnostic symbols.
- Keep existing budget and citation rules unchanged.
- Add explicit fallback path when outline symbols are empty.

**Tests to add/update**
- `tests/unit/bundler/test_multilanguage_outline_consumption.py`
- `tests/integration/test_bundle_with_non_python_outline.py`

**Acceptance criteria**
- Bundler behavior remains deterministic across supported languages.
- Citations and rationale remain complete and schema-stable.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 34 only from TODO.md.
```

### Step 35 - Golden fixtures and determinism hardening for all adapters

**Goal**  
Add comprehensive fixtures and determinism tests for multi-language adapter outputs.

**Required changes**
- Add minimal golden fixtures per language with expected symbol JSON snapshots.
- Add repeat-run determinism assertions for order, ranges, and signatures.
- Add cross-platform path normalization checks in multilingual contexts.

**Tests to add/update**
- `tests/unit/adapters/test_multilanguage_golden_snapshots.py`
- `tests/integration/test_multilanguage_outline_determinism.py`

**Acceptance criteria**
- Golden tests are deterministic and self-contained.
- No test requires network or external compilers.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 35 only from TODO.md.
```

### Step 36 - Documentation updates for language support and limitations

**Goal**  
Update docs to describe language coverage, lexical limitations, and deterministic guarantees.

**Required changes**
- Update `README.md` support matrix for language adapters.
- Update usage docs for `repo.outline` with multilingual examples.
- Document limitations and edge-case behavior per language.

**Tests to add/update**
- Add/adjust doc consistency tests if present.

**Acceptance criteria**
- Supported extensions and limitations are documented accurately.
- Docs do not claim parser/toolchain features not implemented.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 36 only from TODO.md.
```

## M6 - Optional enhanced parsing (gated, post-baseline)

### Step 37 - STOP: tree-sitter adoption decision gate

**Goal**  
Decide whether to adopt tree-sitter as a shared enhanced parser dependency.

**Required changes**
- Do not implement parser integration in this step.
- Prepare decision memo with:
  - dependency footprint and licenses,
  - reproducibility and portability impacts,
  - determinism and maintenance tradeoffs.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Human decision captured explicitly with go/no-go.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 37 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 38 without explicit approval.
```

### Step 38 - STOP: external toolchain integration decision gate (Go/Java/C++/Rust/C#)

**Goal**  
Decide whether optional execution of external compilers/toolchains is permitted.

**Required changes**
- Do not implement external execution in this step.
- Document tradeoffs:
  - hermeticity and reproducibility risk,
  - security/sandbox surface increase,
  - platform/toolchain availability complexity.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Explicit human-approved policy recorded (likely default: disallow).

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 38 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 39 without explicit approval.
```

### Step 39 - STOP: outline-only vs language-aware chunking decision gate

**Goal**  
Decide whether adapter output should remain outline-only or also provide chunking hints.

**Required changes**
- Do not implement chunking changes in this step.
- Record impact analysis on deterministic chunk IDs and backward compatibility.

**Tests to add/update**
- None (decision checkpoint).

**Acceptance criteria**
- Human-approved direction captured before any chunking behavior changes.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 39 only from TODO.md. This is a STOP-and-ask decision gate; collect the decision and do not proceed to Step 40 without explicit approval.
```

### Step 40 - Optional enhanced TS/JS parsing (only if approved)

**Goal**  
Implement approved enhanced parser path for TS/JS behind explicit config gating.

**Required changes**
- Add parser-backed outline path for TS/JS if approved dependency exists.
- Keep lexical adapter as deterministic fallback.
- Add explicit configuration toggle defaulting to lexical mode.

**Tests to add/update**
- `tests/unit/adapters/test_ts_js_enhanced_mode.py`
- Determinism parity tests between lexical and enhanced fallbacks.

**Acceptance criteria**
- Enhanced mode is opt-in and deterministic.
- No behavior change for default lexical mode.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 40 only from TODO.md, and only if Step 37 approval is explicitly recorded.
```

### Step 41 - Optional enhanced Java parsing (only if approved)

**Goal**  
Implement approved enhanced Java parsing path behind explicit config gating.

**Required changes**
- Add parser-backed Java outline path if approved.
- Preserve lexical fallback as default-safe path.
- Document parser-specific limitations and version constraints.

**Tests to add/update**
- `tests/unit/adapters/test_java_enhanced_mode.py`

**Acceptance criteria**
- Default behavior remains lexical and deterministic.
- Enhanced mode is controlled and reproducible.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 41 only from TODO.md, and only if Step 37 approval is explicitly recorded.
```

### Step 42 - Optional enhanced Go/Rust/C++/C# parsing (only if approved)

**Goal**  
Implement approved enhanced parsing path for Go/Rust/C++/C# with strict gating and fallback.

**Required changes**
- Add approved parser/tooling integration for selected languages.
- Keep lexical mode as default and mandatory fallback.
- If external executables are approved, enforce explicit opt-in and deterministic invocation constraints.

**Tests to add/update**
- `tests/unit/adapters/test_go_enhanced_mode.py`
- `tests/unit/adapters/test_rust_enhanced_mode.py`
- `tests/unit/adapters/test_cpp_enhanced_mode.py`
- `tests/unit/adapters/test_csharp_enhanced_mode.py`

**Acceptance criteria**
- No change to default lexical behavior.
- Enhanced paths are deterministic under approved policy and fully tested.

**Command gates**
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

**Prompt**
```text
Implement Step 42 only from TODO.md, and only if Steps 37-39 approvals are explicitly recorded.
```
