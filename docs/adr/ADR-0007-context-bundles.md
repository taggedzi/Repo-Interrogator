## ADR-0007 - Context Bundles as First-Class, Inspectable Artifacts

**Status:** Accepted
**Date:** 2026-02-08

### Context

AI agents benefit from curated context, but humans must be able to understand and audit what the AI used.

### Decision

Context bundles produced by the server are **first-class artifacts**:

* Explicit file paths and line ranges
* Per-excerpt rationale
* Full citation metadata
* Optional human-readable exports

### Rationale

* Builds trust with human developers
* Enables debugging of AI behavior
* Prevents “invisible context” failures
* Supports reproducibility

### Consequences

* Context bundling logic must be transparent
* Tool outputs may be larger but more informative
* Storage and logging must be carefully bounded
