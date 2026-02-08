## ADR-0004 - Python-First with Pluggable Language Adapters

**Status:** Accepted
**Date:** 2026-02-08

### Context

The repository interrogation problem is language-dependent. Python repositories benefit greatly from AST-based structure extraction, while other languages may not be required initially.

### Decision

The system is **Python-first**, but implemented with a **pluggable language adapter architecture**.

* Python receives first-class structural support (AST outlines, symbol ranges)
* Other languages default to lexical search and file access
* Additional adapters can be added without modifying core logic

### Rationale

* Matches the primary development workload
* Avoids premature complexity
* Encourages community or future expansion
* Prevents Python-specific logic from leaking into core systems

### Consequences

* Core logic must remain language-agnostic
* Adapter interfaces must be stable and documented
* Non-Python languages may have reduced feature depth in v1
