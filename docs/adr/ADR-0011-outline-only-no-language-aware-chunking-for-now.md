## ADR-0011 - Keep Adapters Outline-Only (No Language-Aware Chunking for v1)

**Status:** Accepted
**Date:** 2026-02-09

### Context

A decision was required on whether language adapters should influence chunk boundaries.

Options considered:

* keep adapters outline-only
* add optional adapter chunking hints
* make chunking adapter-aware by default

The project already has deterministic global chunking behavior and stable chunk ID expectations.

### Decision

For now, adapters will remain **outline-only**.

The core chunking strategy remains global and language-agnostic.

No adapter-provided chunking hints will be used in v1.

### Rationale

* Preserves deterministic chunking and chunk ID stability
* Avoids compatibility risk in indexing/search/bundling behavior
* Keeps architecture simple and maintainable while multi-language adapter support matures
* Aligns with project intent: safe, deterministic interrogation and retrieval over deep semantic analysis

### Consequences

* Chunk boundaries remain language-agnostic
* Symbol outlines can still improve retrieval context without changing chunk formation
* Potential chunk-quality improvements from language-aware boundaries are deferred
* Future chunking changes require a new explicit decision gate and migration strategy

### Revisit Triggers

Revisit this ADR if one or more of the following becomes true:

* measured chunk quality is a clear bottleneck for retrieval quality
* adapter hints can be introduced without breaking determinism guarantees
* schema/version migration for chunk IDs is planned and approved
