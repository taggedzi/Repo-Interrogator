## ADR-0009 - No Tree-sitter Dependency for v1 Language Adapters

**Status:** Accepted
**Date:** 2026-02-09

### Context

The project expanded language adapter support for TypeScript, JavaScript, Java, Go, Rust, C++, and C#.

A decision was required on whether to adopt tree-sitter for parser-backed outlines now, or keep lexical adapters only.

Current constraints include:

* deterministic behavior as a hard requirement
* minimal dependency footprint
* maintainability by a small team
* practical support scope focused on Windows, WSL, and Linux

### Decision

For now, the project will **not adopt tree-sitter**.

Language adapters remain lexical/deterministic by default, with no new parser runtime dependency added.

Tree-sitter may be reconsidered later if a strong product need is demonstrated.

### Rationale

* Keeps runtime dependencies and packaging complexity low
* Avoids immediate license and dependency-audit burden
* Reduces cross-platform runtime and build variability risk
* Keeps maintenance overhead manageable while feature set stabilizes

### Consequences

* Non-Python outlines remain conservative for complex language constructs
* Some advanced syntax patterns may be partially represented
* Adapter output remains deterministic and dependency-light
* Future parser-backed enhancement remains possible behind a new decision gate

### Revisit Triggers

Revisit this ADR if one or more of the following becomes true:

* lexical outlines materially block important user workflows
* accuracy requirements cannot be met with lexical adapters
* dependency/license review capacity is available
* platform support and CI coverage can reliably absorb parser runtime complexity
