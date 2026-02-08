## ADR-0008 - Tooling Standardization on Ruff (No Black)

**Status:** Accepted
**Date:** 2026-02-08

### Context

Previous projects experienced instability and hangs when using Black in agent-driven environments.

### Decision

The project standardizes on **Ruff for both linting and formatting**.

Black is explicitly excluded.

### Rationale

* Faster execution
* More stable in agent environments
* Single tool for lint + format
* Reduces agent friction and failure modes

### Consequences

* Ruff configuration must be explicit
* Agents must not reintroduce Black
* Formatting behavior must be documented and stable
