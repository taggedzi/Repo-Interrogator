#!/usr/bin/env python3
"""Run optional warning-only perf drift guardrails with baseline bootstrapping."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to cwd.")
    parser.add_argument(
        "--baseline",
        default=".repo_mcp/perf/baselines/local-self.json",
        help="Baseline benchmark summary path used for drift checks.",
    )
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=20.0,
        help="Drift warning threshold percentage. Default: 20.0.",
    )
    parser.add_argument(
        "--scenarios",
        default="self",
        help="Benchmark scenarios to run. Default: self.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Runs per scenario for this guardrail check. Default: 1.",
    )
    parser.add_argument(
        "--retention-sessions",
        type=int,
        default=15,
        help="Number of benchmark sessions to retain. Default: 15.",
    )
    parser.add_argument(
        "--bootstrap-if-missing",
        action="store_true",
        help="Create a baseline from current run if missing, then exit successfully.",
    )
    return parser.parse_args()


def _run_benchmark(
    *,
    repo_root: Path,
    scenarios: str,
    runs: int,
    retention_sessions: int,
    baseline: Path | None,
    threshold_percent: float,
) -> int:
    command = [
        sys.executable,
        "scripts/benchmark_workflow.py",
        "--repo-root",
        str(repo_root),
        "--scenarios",
        scenarios,
        "--runs",
        str(runs),
        "--retention-sessions",
        str(retention_sessions),
    ]
    if baseline is not None:
        command.extend(
            [
                "--regression-baseline",
                str(baseline),
                "--regression-threshold-percent",
                str(threshold_percent),
            ]
        )
    completed = subprocess.run(command, cwd=repo_root, check=False)
    return completed.returncode


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    if args.retention_sessions < 1:
        raise SystemExit("--retention-sessions must be >= 1")
    if args.threshold_percent < 0:
        raise SystemExit("--threshold-percent must be >= 0")

    repo_root = Path(args.repo_root).resolve()
    baseline_path = (repo_root / args.baseline).resolve()
    baseline_exists = baseline_path.exists()

    if baseline_exists:
        return _run_benchmark(
            repo_root=repo_root,
            scenarios=args.scenarios,
            runs=args.runs,
            retention_sessions=args.retention_sessions,
            baseline=baseline_path,
            threshold_percent=float(args.threshold_percent),
        )

    if not args.bootstrap_if_missing:
        print(f"Baseline missing: {baseline_path}", file=sys.stderr)
        print("Hint: rerun with --bootstrap-if-missing to create one.", file=sys.stderr)
        return 2

    print(f"Baseline missing; bootstrapping from current run: {baseline_path}")
    exit_code = _run_benchmark(
        repo_root=repo_root,
        scenarios=args.scenarios,
        runs=args.runs,
        retention_sessions=args.retention_sessions,
        baseline=None,
        threshold_percent=float(args.threshold_percent),
    )
    if exit_code != 0:
        return exit_code

    latest_summary = repo_root / ".repo_mcp" / "perf" / "benchmark_summary.json"
    if not latest_summary.exists():
        print(
            (f"Benchmark completed but latest summary was not found at {latest_summary}."),
            file=sys.stderr,
        )
        return 3

    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(latest_summary, baseline_path)
    print(f"Bootstrapped baseline summary: {baseline_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
