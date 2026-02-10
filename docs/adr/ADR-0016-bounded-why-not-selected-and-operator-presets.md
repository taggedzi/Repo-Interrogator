## ADR-0016 - Bounded Selection-Debug Summary and Operator Preset Guidance

**Status:** Accepted
**Date:** 2026-02-10

### Context

Repo Interrogator now provides deterministic bundle selection explainability (`why_selected`) and ranking debug fields.
Operators requested additional clarity on skipped candidates while preserving deterministic behavior and bounded payloads.

Operators also requested clearer setup guidance for common repository sizes without introducing complex or implicit runtime modes.

### Decision

Adopt two low-risk usability additions:

1. Add an optional bounded diagnostics summary for skipped bundle candidates at:
   - `repo.build_context_bundle.result.audit.selection_debug.why_not_selected_summary`
2. Document recommended non-binding config profiles named:
   - `small`, `medium`, `large`

Operational guidance decision:

* Perf-drift checks remain warning-only by default for local/CI usage.

### Rationale

* Improves human and AI debugging of retrieval gaps without exposing content.
* Keeps explainability compact and deterministic.
* Preserves existing tool contracts and ranking semantics.
* Gives maintainers simple, shared language for tuning without adding heavy runtime policy layers.

### Consequences

* `SPEC.md` must define bounded `why_not_selected` shape and ordering guarantees.
* Diagnostics fields must remain optional and non-invasive to ranking behavior.
* Docs should present `small`/`medium`/`large` as guidance only, not a hidden mode switch.
* CI guidance should avoid hard failures on perf drift by default.

### Non-goals

* No changes to ranking signal math or tie-break ordering from this ADR alone.
* No new always-on telemetry or external observability backend.
* No mandatory CI gate based solely on perf drift warnings.
* No unbounded candidate-debug payloads.

### Revisit Triggers

Revisit if:

* diagnostics payload size becomes a recurring response-size risk,
* users require mandatory quality/perf gates in CI,
* preset guidance needs to become explicit runtime profile objects.
