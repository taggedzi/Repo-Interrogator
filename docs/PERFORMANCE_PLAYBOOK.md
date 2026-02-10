# Performance Playbook

This playbook defines a stable, repeatable process for diagnosing Repo MCP performance bottlenecks.

Scope:
- Benchmark scenarios: `self`, `medium`, `large`
- Artifact root: `.repo_mcp/perf/`
- Goal: identify bottlenecks before proposing optimizations

## 1) Standard Protocol

1. Run baseline benchmark:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root .
```

2. Run references-targeted benchmark:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --profile-references
```

3. Run bundler-targeted benchmark:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --profile-bundler
```

4. Run optional non-blocking regression guardrails against a saved baseline:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --regression-baseline .repo_mcp/perf/benchmark_summary.json --regression-threshold-percent 20
```

Baseline usage pattern (recommended):

1. Capture and retain a baseline snapshot:

```bash
mkdir -p .repo_mcp/perf/baselines
cp .repo_mcp/perf/benchmark_summary.json .repo_mcp/perf/baselines/local-self.json
```

2. Run warning-only drift checks against that fixed baseline:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --scenarios self --runs 1 --regression-baseline .repo_mcp/perf/baselines/local-self.json --regression-threshold-percent 20
```

3. Optional helper wrapper (bootstraps baseline if missing):

```bash
.venv/bin/python scripts/perf_guardrail_check.py --repo-root . --baseline .repo_mcp/perf/baselines/local-self.json --bootstrap-if-missing
```

5. If software hotspots are unclear, capture workflow `cProfile`:

```bash
.venv/bin/python scripts/validate_workflow.py --repo-root . --profile --cprofile-output .repo_mcp/perf/validate_profile.pstats
```

6. If client `cProfile` is mostly wait time, capture server-process `cProfile`:

```bash
.venv/bin/python scripts/validate_workflow.py --repo-root . --profile --server-cprofile-output .repo_mcp/perf/server_profile.pstats
```

Protocol rules:
- Keep benchmark defaults unless intentionally testing overrides (default runs per scenario: 3).
- Compare sessions generated on the same machine state when possible.
- Preserve artifacts for before/after comparisons; avoid deleting session history during diagnosis.
- Treat guardrail warnings as triage input; they are intentionally non-blocking.
- Prefer checking against a fixed retained baseline, not the mutable "latest summary" path.

## 2) Artifact Map

- Session directories: `.repo_mcp/perf/session-*/`
- Latest summary: `.repo_mcp/perf/benchmark_summary.json`
- Baseline per-run profile artifacts: `profile_run_*.json`
- References-targeted artifacts: `references_run_*.jsonl`
- Bundler-targeted artifacts: `bundler_run_*.jsonl`
- Guardrail results: `regression_guardrails` object in each benchmark summary JSON

## 3) Hardware vs Software Triage

Treat this as a decision checklist:

1. Hardware pressure signals:
- High `load_average` relative to CPU count
- Large `max_rss_kb` growth across similar runs
- Wide variance between repeated runs under same scenario

2. Software bottleneck signals:
- Stable but high `total_elapsed_seconds`
- One step consistently dominates scenario totals
- Targeted slices (`candidate_discovery`, `adapter_resolution`, `ranking`, `budget_enforcement`) dominate their profiles

Interpretation guidance:
- High variance + high load pressure usually indicates host contention or resource limits.
- Low variance + consistently high step timing usually indicates code-path bottlenecks.

## 4) Metric-to-Code Path Mapping

- High `repo.references` candidate discovery timing:
  - Inspect shared file discovery filters and scope (`path`, allow/deny policy checks, file read volume).
- High `repo.references` adapter resolution timing:
  - Inspect adapter selection and resolver normalization/sort behavior.
- High bundler ranking timing:
  - Inspect ranking signal computation and reference proximity lookups.
- High bundler budget enforcement timing:
  - Inspect selection/truncation path and dedupe/budget loops.

## 5) Comparison Template

For each investigation, record:
- session IDs compared
- scenario(s) compared
- command flags used
- key deltas (total and dominant step)
- classification: `hardware`, `software`, or `mixed`
- next action hypothesis

This template keeps decisions auditable and prevents ad hoc interpretation drift.

## 6) Common Pitfalls

- Comparing runs from different machine load conditions without noting it.
- Changing scenario set and treating results as directly comparable.
- Reading only total time without checking targeted profile slices.
- Optimizing before establishing a stable baseline.
