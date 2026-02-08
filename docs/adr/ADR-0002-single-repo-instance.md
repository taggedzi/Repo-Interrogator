## ADR-0002 - Single-Repository Server Instance Model

**Status:** Accepted
**Date:** 2026-02-08

### Context

The MCP server must operate over a codebase. Two models were considered:

* Single repository per server instance
* Multi-repository server with switching or routing

### Decision

Each MCP server instance operates on **exactly one repository**, defined at startup via `repo_root`.

### Rationale

* Stronger sandboxing and security guarantees
* Simpler mental model for agents and humans
* Avoids cross-repo leakage risks
* Reduces implementation complexity in v1

### Consequences

* One server process per repository
* Multi-repo workflows can be handled by multiple server instances
* Repo context is implicit and does not need to be passed per request
