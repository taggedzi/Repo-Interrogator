## ADR-0005 - STDIO-Only MCP Transport for v1

**Status:** Accepted
**Date:** 2026-02-08

### Context

MCP supports multiple transports, including STDIO and HTTP/SSE. For local IDE integration, simplicity and reliability are critical.

### Decision

The MCP server will support **STDIO transport only in v1**.

### Rationale

* Simplest and most reliable integration with Codex
* No networking, ports, or firewall concerns
* Lower attack surface
* Easier debugging and testing

### Consequences

* Server is launched as a subprocess
* No remote access in v1
* HTTP/SSE may be added later without affecting core logic
