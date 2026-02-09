## ADR-0010 - Disallow External Toolchain Integration for v1 Adapters

**Status:** Accepted
**Date:** 2026-02-09

### Context

A decision was required on whether language adapters may invoke external executables such as:

* `go`
* `javac`
* `clang`
* `rustc`
* other compiler/toolchain binaries

This would potentially improve outline accuracy for some languages, but introduces runtime coupling to local toolchains and platform-specific behavior.

### Decision

For now, the project will **disallow external toolchain integration** in adapter/runtime paths.

Language adapters must remain in-process and deterministic without invoking external executables.

### Rationale

* Primary product intent is deterministic repository interrogation and search for LLM workflows, not full semantic language analysis
* The server is designed to help an LLM find and retrieve the right code evidence efficiently
* Adapters provide lightweight structural hints, but core responsibility remains search, indexing, and safe retrieval
* Avoids expanding sandbox and security surface area
* Avoids cross-platform dependency drift and missing-tool failures
* Keeps maintenance and CI complexity manageable for current support scope (Windows, WSL, Linux)

### Consequences

* The project remains focused on evidence retrieval over deep parser semantics
* Adapter behavior is deterministic and independent of local compiler installation
* Some advanced syntax cases remain only partially represented by lexical adapters
* Any future external-tool integration requires a new explicit decision gate and policy update

### Revisit Triggers

Revisit this ADR if one or more of the following becomes true:

* lexical/in-process outlines materially block important user workflows
* a strict opt-in external-tool mode can be proven deterministic and safely sandboxed
* platform support, CI coverage, and maintenance capacity can absorb toolchain variance
