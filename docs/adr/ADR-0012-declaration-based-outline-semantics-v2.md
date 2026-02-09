## ADR-0012 - Declaration-Based Outline Semantics (Nested + Conditional) for v2

**Status:** Proposed
**Date:** 2026-02-09

### Context

The project goal is to help LLM clients interrogate repositories safely and deterministically.
Current outline behavior is useful but can miss legitimate declarations when they are nested or placed inside conditional/control-flow blocks.

This creates retrieval blind spots for realistic codebases that use:

* nested functions/classes
* declarations under `if`, `try`, `match`, and similar constructs
* guard blocks like `if TYPE_CHECKING:`

Options considered:

* keep top-level-only outlines
* include all syntactic declarations (nested + conditional), without runtime evaluation

### Decision

Adopt declaration-based outline semantics for v2 across adapters.

Rules:

* Include syntactically declared symbols, including nested and conditional declarations.
* Do not execute code and do not evaluate runtime branch truth.
* Keep deterministic ordering and stable output contracts.
* Add optional symbol metadata to encode context:
  * `parent_symbol`
  * `scope_kind`
  * `is_conditional`
  * `decl_context`

Compatibility approach:

* Existing symbol fields remain valid.
* New fields are optional in schema and may be populated incrementally per adapter.

### Rationale

* Improves interrogation coverage for real-world repositories.
* Preserves safety and determinism (static parsing only).
* Makes ambiguity explicit through metadata rather than hidden assumptions.
* Supports cross-language adapter evolution without core architectural drift.

### Consequences

* Outline result sets may grow in size.
* Clients can reason better about symbol provenance and confidence.
* Adapters need additional traversal and tests for nested/control-flow cases.
* Some languages will provide richer metadata than others initially; contract remains stable.

### Revisit Triggers

Revisit this ADR if one or more of the following becomes true:

* output volume materially harms performance or usability
* deterministic ordering becomes difficult to guarantee across platforms
* clients require stricter guarantees for runtime-reachable declarations only
* schema migration pressure suggests separating nested/conditional symbols into a dedicated tool
