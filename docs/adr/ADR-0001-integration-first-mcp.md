## ADR-0001 - Integration-First MCP Server Architecture

**Status:** Accepted
**Date:** 2026-02-08

### Context

The goal of Repo Interrogator is to improve AI-assisted coding in large repositories by automating repository interrogation (searching, outlining, context selection) rather than relying on humans to manually prepare context.

Two architectural approaches were considered:

* CLI-first tooling where humans run commands and feed outputs to AI
* Integration-first tooling where AI agents directly interrogate the repository via MCP

### Decision

The project adopts an **integration-first architecture**, where the MCP server is the primary product surface.

AI clients (Codex VS Code, Codex CLI, agents) connect directly to the MCP server to explore the repository and assemble context. Humans may inspect results, but are not required to manually invoke tooling prior to AI usage.

### Rationale

* Reduces human friction and failure points
* Aligns with agent-driven workflows
* Keeps humans out of the “context middleman” role
* Enables automation while preserving auditability

### Consequences

* No CLI UX guarantees are required in v1
* Tool schemas and MCP stability become part of the API contract
* Human visibility is optional and inspectable, not mandatory
