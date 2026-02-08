## ADR-0006 - Strong Repo Sandboxing and Deny-by-Default File Access

**Status:** Accepted
**Date:** 2026-02-08

### Context

Allowing AI agents to read repository files carries security risks, including accidental exposure of secrets or filesystem traversal.

### Decision

The server enforces **strict sandboxing**:

* All file access is restricted to `repo_root`
* Path traversal and symlink escapes are blocked
* Sensitive files are denylisted by default
* Blocking is preferred over redaction

### Rationale

* Prevents accidental data leaks
* Keeps security boundaries explicit
* Easier to reason about than partial redaction
* Aligns with “safe by default” philosophy

### Consequences

* Some reads may be blocked even if useful
* Agents must handle blocked responses gracefully
* Future opt-in relaxation must be explicit and documented
