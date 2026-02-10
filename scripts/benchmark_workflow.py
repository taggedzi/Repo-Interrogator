#!/usr/bin/env python3
"""Run repeatable self-repo workflow benchmarks and write aggregate artifacts."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class BenchmarkRun:
    """One benchmark run result."""

    run_index: int
    exit_code: int
    elapsed_seconds: float
    profile_path: Path
    total_elapsed_seconds: float | None
    steps: dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to benchmark. Defaults to current directory.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of benchmark runs to execute. Default: 3.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for benchmark artifacts. Default: <repo_root>/.repo_mcp/perf/",
    )
    parser.add_argument(
        "--response-timeout-seconds",
        type=float,
        default=180.0,
        help="Per-response timeout forwarded to validate_workflow.py. Default: 180.",
    )
    return parser.parse_args()


def run_one(
    repo_root: Path,
    out_dir: Path,
    run_index: int,
    response_timeout_seconds: float,
) -> BenchmarkRun:
    profile_path = out_dir / f"run_{run_index:02d}.json"
    cmd = [
        sys.executable,
        "scripts/validate_workflow.py",
        "--repo-root",
        str(repo_root),
        "--profile",
        "--profile-output",
        str(profile_path),
        "--response-timeout-seconds",
        str(response_timeout_seconds),
    ]
    print(f"[run {run_index}] $ {' '.join(cmd)}")
    started = time.perf_counter()
    completed = subprocess.run(cmd, check=False)
    elapsed = time.perf_counter() - started

    total_elapsed_seconds: float | None = None
    steps: dict[str, float] = {}
    if profile_path.exists():
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        raw_total = payload.get("total_elapsed_seconds")
        if isinstance(raw_total, (float, int)):
            total_elapsed_seconds = float(raw_total)
        raw_steps = payload.get("steps", [])
        if isinstance(raw_steps, list):
            for item in raw_steps:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("elapsed_seconds")
                if isinstance(name, str) and isinstance(value, (float, int)):
                    steps[name] = float(value)

    return BenchmarkRun(
        run_index=run_index,
        exit_code=completed.returncode,
        elapsed_seconds=elapsed,
        profile_path=profile_path,
        total_elapsed_seconds=total_elapsed_seconds,
        steps=steps,
    )


def summarize(runs: list[BenchmarkRun]) -> dict[str, object]:
    totals = [item.total_elapsed_seconds for item in runs if item.total_elapsed_seconds is not None]
    step_names = sorted({step for run in runs for step in run.steps.keys()})
    step_stats: dict[str, dict[str, float]] = {}
    for step in step_names:
        values = [run.steps[step] for run in runs if step in run.steps]
        if not values:
            continue
        step_stats[step] = {
            "min_seconds": min(values),
            "max_seconds": max(values),
            "mean_seconds": statistics.fmean(values),
        }

    total_stats: dict[str, float] | None = None
    if totals:
        total_stats = {
            "min_seconds": min(totals),
            "max_seconds": max(totals),
            "mean_seconds": statistics.fmean(totals),
        }

    return {
        "runs": len(runs),
        "failures": [run.run_index for run in runs if run.exit_code != 0],
        "total_elapsed_seconds": total_stats,
        "step_elapsed_seconds": step_stats,
        "run_profiles": [str(run.profile_path) for run in runs],
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")

    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (repo_root / ".repo_mcp" / "perf")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_results = [
        run_one(
            repo_root=repo_root,
            out_dir=out_dir,
            run_index=index,
            response_timeout_seconds=args.response_timeout_seconds,
        )
        for index in range(1, args.runs + 1)
    ]

    summary = summarize(run_results)
    summary_path = out_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print("\n=== Benchmark Summary ===")
    total_stats = summary.get("total_elapsed_seconds")
    if isinstance(total_stats, dict):
        print(
            "total_elapsed_seconds: "
            f"min={total_stats['min_seconds']:.3f}, "
            f"max={total_stats['max_seconds']:.3f}, "
            f"mean={total_stats['mean_seconds']:.3f}"
        )
    failures = summary.get("failures", [])
    print(f"failed_runs: {failures}")
    step_stats = summary.get("step_elapsed_seconds", {})
    if isinstance(step_stats, dict):
        for name in sorted(step_stats.keys()):
            values = step_stats[name]
            if not isinstance(values, dict):
                continue
            print(
                f"- {name}: min={values['min_seconds']:.3f}s, "
                f"max={values['max_seconds']:.3f}s, "
                f"mean={values['mean_seconds']:.3f}s"
            )
    print(f"summary_json: {summary_path}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
