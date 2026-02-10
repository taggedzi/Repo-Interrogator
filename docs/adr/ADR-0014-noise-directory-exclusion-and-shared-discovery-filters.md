## ADR-0014 - Noise Directory Exclusion and Shared Discovery Filters

**Status:** Proposed  
**Date:** 2026-02-10

### Context

`repo.references` previously scanned nearly all readable files under `repo_root` when no `path` scope was provided.
In repositories with many cache/build/tooling directories, this increased latency and introduced retrieval noise not useful for source interrogation.

The project goal is deterministic, auditable, local-first repository interrogation focused on source and relevant configuration.

### Decision

Adopt a shared deterministic discovery policy for indexing and unscoped references:

* `repo.references` (without `path`) must use the same file discovery filters as indexing:
  * `index.include_extensions`
  * `index.exclude_globs`
  * deterministic binary-file exclusion
* Expand default `index.exclude_globs` to skip common non-project directories, including:
  * VCS/internal: `.git`, `.repo_mcp`
  * CI metadata: `.github`
  * Python cache/tooling: `__pycache__`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.nox`
  * JS/TS cache/tooling: `node_modules`, `.pnpm-store`, `.yarn`, `.npm`, `.next`, `.nuxt`, `.svelte-kit`
  * JVM/IDE/editor: `.gradle`, `.idea`, `.vscode`
  * Build/output/temp: `dist`, `build`, `target`, `bin`, `obj`, `out`, `coverage`, `tmp`, `temp`
* Expand default `index.include_extensions` for v2.5 language coverage (`.ts/.tsx/.js/.jsx/.java/.go/.rs/.c/.h/.cc/.hh/.cpp/.hpp/.cxx/.cs`) alongside existing Python/docs/config extensions.

### Rationale

* Keeps retrieval focused on source/config instead of tool artifacts.
* Improves reference and bundle latency on real repositories with large cache trees.
* Preserves determinism by using one canonical discovery pipeline.
* Keeps behavior configurable via `repo_mcp.toml` for repos that intentionally store source-of-truth content in excluded paths.

### Consequences

* Default behavior skips more directories than before.
* Some repos may need to override `index.exclude_globs` if they intentionally keep relevant source in excluded paths.
* Index/search and unscoped references now have aligned candidate sets by default.

### Revisit Triggers

Revisit this ADR if:

* exclusion defaults hide commonly needed source-of-truth content across many users
* performance remains unacceptable despite shared filtering
* adapter-specific discovery policies become necessary and can be added without breaking deterministic contracts
