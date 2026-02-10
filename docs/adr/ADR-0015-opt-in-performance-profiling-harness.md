## ADR-0015 - Opt-in Performance Profiling Harness

**Status:** Proposed  
**Date:** 2026-02-10

### Context

Repository interrogation workflows can still exhibit significant latency even in small repositories due to indexing, references, and bundling interactions.
Diagnosing bottlenecks requires repeatable profiling that captures both workflow-step timings and Python-level hotspots.

The project must preserve deterministic behavior and avoid introducing always-on telemetry or external dependencies.

### Decision

Adopt a built-in, opt-in profiling harness centered on `scripts/validate_workflow.py`:

* Add per-step and total elapsed timing in the validator workflow.
* Add bounded host/process snapshot metadata for context:
  * platform
  * Python version
  * logical CPU count
  * load average where available
  * process max RSS where available
* Add optional JSON profile artifact output for historical comparison.
* Add optional `cProfile` `.pstats` output for software hotspot analysis.
* Keep profiling disabled by default and explicitly enabled via CLI flags.
* Adopt benchmark execution defaults:
  * scenario matrix: `self`, `medium`, `large`
  * 3 runs per scenario per benchmark invocation
  * artifacts stored under `<repo_root>/.repo_mcp/perf/` in sessioned directories
  * configurable retention with deterministic pruning of older `session-*` directories
* Add targeted `repo.references` profiling mode that captures:
  * candidate discovery timing slices
  * adapter resolution timing slices
  * per-run JSONL artifacts retained with benchmark sessions

### Rationale

* Produces repeatable diagnostics without changing runtime behavior by default.
* Supports both coarse bottleneck localization (step timings) and fine-grained Python analysis (`cProfile`).
* Uses standard library only, preserving dependency posture and portability.

### Consequences

* Profiling runs are slightly more complex to operate due to mode flags and artifacts.
* Additional documentation and fixture-generation logic are required to operationalize scenario benchmarking and regression gates.
* Hardware-level counters remain limited to what is safely available from standard library and host OS APIs.

### Revisit Triggers

Revisit this ADR if:

* profiling overhead materially distorts measured outcomes
* maintainers need richer hardware counters beyond standard library support
* continuous performance regression gates become required in CI
