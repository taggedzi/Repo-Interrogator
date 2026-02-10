## ADR-0013 - Deterministic Cross-File References for v2.5

**Status:** Proposed
**Date:** 2026-02-10

### Context

Repo Interrogator currently provides deterministic indexing, search, file opening, and declaration outlines.
For multi-file impact analysis, users need deterministic "where used" style evidence across files.

Without cross-file reference outputs, clients must infer usage links manually from search hits, which reduces reliability and increases review time.

### Decision

Adopt deterministic cross-file references in v2.5 with a Python-first extraction strategy and lexical fallback for other supported languages.

Contract decisions:

* Introduce a dedicated `repo.references` API surface.
* Return declaration-linked, best-effort references with explicit strategy/confidence fields.
* Keep output ordering and truncation deterministic and auditable.
* Do not execute code and do not evaluate runtime branch truth.

Extraction strategy:

* Python: AST-first extraction and linking.
* TS/JS/Java/Go/Rust/C++/C#: lexical fallback in v2.5.

### Non-goals

* Full semantic call graph precision across all languages in v2.5.
* Runtime-aware branch resolution.
* Any LLM-assisted reference inference.
* External compiler/toolchain execution for reference extraction.

### Rationale

* Aligns with project purpose: reliable repository interrogation for AI clients.
* Preserves deterministic and auditable behavior.
* Delivers high-value impact analysis with incremental implementation risk.
* Keeps Python-first depth while maintaining cross-language coverage via fallback.

### Consequences

* Reference outputs are best effort and may include false positives/negatives, especially in lexical fallback modes.
* New schema fields and limits must be tested and documented.
* Bundle ranking can use references for better relevance while remaining deterministic.

### Revisit Triggers

Revisit this ADR if one or more of the following becomes true:

* lexical fallback precision becomes a major workflow blocker
* deterministic output limits are too restrictive for practical usage
* users require stronger semantic precision than in-process deterministic methods can provide
* tool schema pressure suggests splitting reference kinds into specialized endpoints
