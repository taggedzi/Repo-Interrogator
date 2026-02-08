## ADR-0003 - Deterministic-Only Server Behavior (No LLM Calls)

**Status:** Accepted
**Date:** 2026-02-08

### Context

Modern AI systems increasingly rely on LLM-driven retrieval, reasoning, and context selection. However, embedding LLM calls inside infrastructure services introduces nondeterminism, cost variability, and hidden behavior.

### Decision

In v1, the MCP server **must not call any LLMs**.

All indexing, searching, outlining, and context bundling logic is **fully deterministic**.

### Rationale

* Predictable and reproducible behavior
* Easier debugging and auditing
* Clear separation of concerns (infrastructure vs reasoning)
* Avoids cost and availability coupling to model providers

### Consequences

* Context bundling uses heuristics, ranking, and adapters
* AI clients are responsible for reasoning and decision-making
* Server architecture must remain future-ready for optional LLM-assisted bundling, but without v1 behavior changes
