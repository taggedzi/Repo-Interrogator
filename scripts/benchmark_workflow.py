#!/usr/bin/env python3
"""Run deterministic benchmark scenarios for validate_workflow.py."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_SCENARIOS = ("self", "medium", "large")
SCENARIO_NAMES = frozenset(DEFAULT_SCENARIOS)


@dataclass(frozen=True, slots=True)
class FixtureProfile:
    """Size profile for a generated benchmark fixture repository."""

    packages: int
    modules_per_package: int
    docs_files: int
    helper_files_per_package: int
    statements_per_module: int


@dataclass(slots=True)
class BenchmarkRun:
    """One benchmark run result."""

    scenario: str
    run_index: int
    exit_code: int
    elapsed_seconds: float
    profile_path: Path
    references_profile_path: Path | None
    total_elapsed_seconds: float | None
    steps: dict[str, float]
    references_metrics: dict[str, float]


FIXTURE_PROFILES: dict[str, FixtureProfile] = {
    "medium": FixtureProfile(
        packages=12,
        modules_per_package=12,
        docs_files=24,
        helper_files_per_package=4,
        statements_per_module=20,
    ),
    "large": FixtureProfile(
        packages=24,
        modules_per_package=16,
        docs_files=48,
        helper_files_per_package=6,
        statements_per_module=24,
    ),
}


def parse_scenarios(raw: str) -> list[str]:
    names = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not names:
        raise SystemExit("At least one scenario is required.")
    unknown = sorted({name for name in names if name not in SCENARIO_NAMES})
    if unknown:
        raise SystemExit(f"Unknown scenarios: {unknown}. Allowed: {sorted(SCENARIO_NAMES)}.")
    ordered_unique: list[str] = []
    for name in names:
        if name not in ordered_unique:
            ordered_unique.append(name)
    return ordered_unique


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used by the self scenario. Defaults to current directory.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of benchmark runs to execute per scenario. Default: 3.",
    )
    parser.add_argument(
        "--scenarios",
        default="self,medium,large",
        help="Comma-separated scenario list. Allowed: self,medium,large.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output root for benchmark artifacts. Default: <repo_root>/.repo_mcp/perf/",
    )
    parser.add_argument(
        "--fixtures-root",
        default=None,
        help=("Fixture repository root for generated scenarios. Default: <out-dir>/fixtures/"),
    )
    parser.add_argument(
        "--rebuild-fixtures",
        action="store_true",
        help="Rebuild generated fixture repositories even if they already exist.",
    )
    parser.add_argument(
        "--retention-sessions",
        type=int,
        default=10,
        help="Number of newest session-* directories to retain. Default: 10.",
    )
    parser.add_argument(
        "--response-timeout-seconds",
        type=float,
        default=180.0,
        help="Per-response timeout forwarded to validate_workflow.py. Default: 180.",
    )
    parser.add_argument(
        "--profile-references",
        action="store_true",
        help=(
            "Enable targeted repo.references profiling (candidate discovery and adapter "
            "resolution timings) and include per-run artifacts in session output."
        ),
    )
    return parser.parse_args()


def generate_server_stub() -> str:
    return (
        textwrap.dedent(
            '''
        """Fixture server module used for benchmark scenario generation."""

        from __future__ import annotations

        from dataclasses import dataclass


        @dataclass(slots=True)
        class Request:
            request_id: str
            method: str
            params: dict[str, object]


        class StdioServer:
            """Small deterministic shape compatible with workflow checks."""

            def serve(self, line: str) -> str:
                return self.handle_payload({"line": line})

            def handle_json_line(self, payload: str) -> str:
                request = self.parse_request(payload)
                return self.handle_payload({"request": request})

            def parse_request(self, payload: object) -> Request:
                return Request(
                    request_id="fixture",
                    method="repo.status",
                    params={"payload": payload},
                )

            def handle_payload(self, payload: object) -> str:
                if isinstance(payload, dict):
                    return f"ok:{sorted(payload.keys())}"
                return "ok:payload"
        '''
        ).strip()
        + "\n"
    )


def module_text(package_idx: int, module_idx: int, statements_per_module: int) -> str:
    lines = [
        f'"""Generated benchmark module {package_idx:03d}_{module_idx:03d}."""',
        "",
        "from __future__ import annotations",
        "",
        f"class GeneratedHandler{package_idx:03d}_{module_idx:03d}:",
        '    """Deterministic generated class used by benchmark fixtures."""',
        "",
        "    def __init__(self, seed: int) -> None:",
        "        self.seed = seed",
        "",
        "    def route(self, request: str) -> str:",
        "        state = []",
    ]
    for offset in range(statements_per_module):
        lines.append(
            f'        state.append("pkg{package_idx:03d}-mod{module_idx:03d}-'
            f'step{offset:02d}-server-request-routing-search-flow")'
        )
    lines.extend(
        [
            '        state.append(f"request:{request}")',
            '        return "|".join(state)',
            "",
            f"def run_{package_idx:03d}_{module_idx:03d}(query: str) -> str:",
            (
                f"    handler = GeneratedHandler{package_idx:03d}_{module_idx:03d}"
                f"(seed={package_idx + module_idx})"
            ),
            "    return handler.route(query)",
            "",
        ]
    )
    return "\n".join(lines)


def helper_text(package_idx: int, helper_idx: int) -> str:
    return (
        textwrap.dedent(
            f"""
        \"\"\"Generated helper {package_idx:03d}_{helper_idx:03d}.\"\"\"

        from __future__ import annotations


        def build_tokens() -> list[str]:
            tokens = [
                "server",
                "request",
                "routing",
                "search",
                "flow",
                "package-{package_idx:03d}",
                "helper-{helper_idx:03d}",
            ]
            return sorted(tokens)
        """
        ).strip()
        + "\n"
    )


def doc_text(doc_idx: int) -> str:
    return (
        textwrap.dedent(
            f"""
        # Benchmark Document {doc_idx:03d}

        This deterministic fixture document exists to increase discovery and bundling work.
        Keywords: server request routing search flow deterministic benchmark scenario.
        """
        ).strip()
        + "\n"
    )


def write_fixture_repo(
    fixture_root: Path,
    profile: FixtureProfile,
    profile_name: str,
    source_repo_root: Path,
) -> None:
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True, exist_ok=True)

    src_root = fixture_root / "src"
    docs_root = fixture_root / "docs"
    src_root.mkdir(parents=True, exist_ok=True)
    docs_root.mkdir(parents=True, exist_ok=True)

    server_target = fixture_root / "src" / "repo_mcp"
    server_target.mkdir(parents=True, exist_ok=True)
    source_server = source_repo_root / "src" / "repo_mcp" / "server.py"
    if source_server.exists():
        server_target.joinpath("server.py").write_text(
            source_server.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    else:
        server_target.joinpath("server.py").write_text(
            generate_server_stub(),
            encoding="utf-8",
        )
    server_target.joinpath("__init__.py").write_text("", encoding="utf-8")

    for package_idx in range(profile.packages):
        package_name = f"generated_pkg_{package_idx:03d}"
        package_dir = src_root / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        package_dir.joinpath("__init__.py").write_text("", encoding="utf-8")
        for helper_idx in range(profile.helper_files_per_package):
            helper_path = package_dir / f"helper_{helper_idx:03d}.py"
            helper_path.write_text(
                helper_text(package_idx=package_idx, helper_idx=helper_idx),
                encoding="utf-8",
            )
        for module_idx in range(profile.modules_per_package):
            module_path = package_dir / f"module_{module_idx:03d}.py"
            module_path.write_text(
                module_text(
                    package_idx=package_idx,
                    module_idx=module_idx,
                    statements_per_module=profile.statements_per_module,
                ),
                encoding="utf-8",
            )

    for doc_idx in range(profile.docs_files):
        (docs_root / f"scenario_{profile_name}_{doc_idx:03d}.md").write_text(
            doc_text(doc_idx),
            encoding="utf-8",
        )

    fixture_root.joinpath("README.md").write_text(
        (
            f"# Benchmark Fixture ({profile_name})\n\n"
            "Generated deterministic fixture repository for benchmark scenarios.\n"
        ),
        encoding="utf-8",
    )
    fixture_root.joinpath("repo_mcp.toml").write_text(
        textwrap.dedent(
            """
            [index]
            include_extensions = [".py", ".md", ".toml", ".json", ".yaml", ".yml"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    fixture_root.joinpath(".fixture_profile.json").write_text(
        json.dumps(
            {
                "profile_name": profile_name,
                "profile": {
                    "packages": profile.packages,
                    "modules_per_package": profile.modules_per_package,
                    "docs_files": profile.docs_files,
                    "helper_files_per_package": profile.helper_files_per_package,
                    "statements_per_module": profile.statements_per_module,
                },
                "generated_at_utc": datetime.now(UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def ensure_fixture_repo(
    fixtures_root: Path,
    scenario: str,
    source_repo_root: Path,
    rebuild: bool,
) -> Path:
    profile = FIXTURE_PROFILES[scenario]
    fixture_root = fixtures_root / scenario
    marker_path = fixture_root / ".fixture_profile.json"
    if rebuild or not marker_path.exists():
        write_fixture_repo(
            fixture_root=fixture_root,
            profile=profile,
            profile_name=scenario,
            source_repo_root=source_repo_root,
        )
        return fixture_root

    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        write_fixture_repo(
            fixture_root=fixture_root,
            profile=profile,
            profile_name=scenario,
            source_repo_root=source_repo_root,
        )
        return fixture_root

    saved_profile = marker.get("profile")
    expected_profile = {
        "packages": profile.packages,
        "modules_per_package": profile.modules_per_package,
        "docs_files": profile.docs_files,
        "helper_files_per_package": profile.helper_files_per_package,
        "statements_per_module": profile.statements_per_module,
    }
    if saved_profile != expected_profile:
        write_fixture_repo(
            fixture_root=fixture_root,
            profile=profile,
            profile_name=scenario,
            source_repo_root=source_repo_root,
        )
    return fixture_root


def run_one(
    scenario: str,
    repo_root: Path,
    scenario_out_dir: Path,
    run_index: int,
    response_timeout_seconds: float,
    profile_references: bool,
) -> BenchmarkRun:
    profile_path = scenario_out_dir / f"run_{run_index:02d}.json"
    references_profile_path: Path | None = None
    references_source_path = repo_root / ".repo_mcp" / "perf" / "references_profile.jsonl"
    if profile_references and references_source_path.exists():
        references_source_path.unlink()
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
    if profile_references:
        cmd.append("--profile-references")
    print(f"[{scenario} run {run_index}] $ {' '.join(cmd)}")
    started = time.perf_counter()
    completed = subprocess.run(cmd, check=False)
    elapsed = time.perf_counter() - started

    total_elapsed_seconds: float | None = None
    steps: dict[str, float] = {}
    references_metrics: dict[str, float] = {}
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
    if profile_references and references_source_path.exists():
        references_profile_path = scenario_out_dir / f"references_run_{run_index:02d}.jsonl"
        shutil.copy2(references_source_path, references_profile_path)
        references_metrics = summarize_reference_profile(references_profile_path)

    return BenchmarkRun(
        scenario=scenario,
        run_index=run_index,
        exit_code=completed.returncode,
        elapsed_seconds=elapsed,
        profile_path=profile_path,
        references_profile_path=references_profile_path,
        total_elapsed_seconds=total_elapsed_seconds,
        steps=steps,
        references_metrics=references_metrics,
    )


def _summarize_metric(values: list[float]) -> dict[str, float]:
    return {
        "min_seconds": min(values),
        "max_seconds": max(values),
        "mean_seconds": statistics.fmean(values),
    }


def summarize_reference_profile(path: Path) -> dict[str, float]:
    metrics: dict[str, float] = {}
    if not path.exists():
        return metrics
    candidate_discovery_seconds: list[float] = []
    discover_files_seconds: list[float] = []
    policy_seconds: list[float] = []
    read_files_seconds: list[float] = []
    adapter_select_seconds: list[float] = []
    resolver_seconds: list[float] = []
    normalize_sort_seconds: list[float] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            candidate_discovery = record.get("candidate_discovery")
            if isinstance(candidate_discovery, dict):
                discovery_value = candidate_discovery.get("candidate_discovery_seconds")
                if isinstance(discovery_value, (int, float)):
                    candidate_discovery_seconds.append(float(discovery_value))
                discover_value = candidate_discovery.get("discover_files_seconds")
                if isinstance(discover_value, (int, float)):
                    discover_files_seconds.append(float(discover_value))
                policy_value = candidate_discovery.get("policy_seconds")
                if isinstance(policy_value, (int, float)):
                    policy_seconds.append(float(policy_value))
                read_value = candidate_discovery.get("read_files_seconds")
                if isinstance(read_value, (int, float)):
                    read_files_seconds.append(float(read_value))
            adapter_resolution = record.get("adapter_resolution")
            if isinstance(adapter_resolution, dict):
                select_value = adapter_resolution.get("adapter_select_seconds")
                if isinstance(select_value, (int, float)):
                    adapter_select_seconds.append(float(select_value))
                resolver_value = adapter_resolution.get("resolver_seconds")
                if isinstance(resolver_value, (int, float)):
                    resolver_seconds.append(float(resolver_value))
                normalize_value = adapter_resolution.get("normalize_sort_seconds")
                if isinstance(normalize_value, (int, float)):
                    normalize_sort_seconds.append(float(normalize_value))
    metrics["records"] = float(len(candidate_discovery_seconds) or len(adapter_select_seconds))
    if candidate_discovery_seconds:
        metrics["candidate_discovery_seconds_mean"] = statistics.fmean(candidate_discovery_seconds)
    if discover_files_seconds:
        metrics["discover_files_seconds_mean"] = statistics.fmean(discover_files_seconds)
    if policy_seconds:
        metrics["policy_seconds_mean"] = statistics.fmean(policy_seconds)
    if read_files_seconds:
        metrics["read_files_seconds_mean"] = statistics.fmean(read_files_seconds)
    if adapter_select_seconds:
        metrics["adapter_select_seconds_mean"] = statistics.fmean(adapter_select_seconds)
    if resolver_seconds:
        metrics["resolver_seconds_mean"] = statistics.fmean(resolver_seconds)
    if normalize_sort_seconds:
        metrics["normalize_sort_seconds_mean"] = statistics.fmean(normalize_sort_seconds)
    return metrics


def summarize_runs(runs: list[BenchmarkRun]) -> dict[str, object]:
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

    reference_metric_names = sorted(
        {
            metric_name
            for run in runs
            for metric_name in run.references_metrics.keys()
            if metric_name != "records"
        }
    )
    references_stats: dict[str, dict[str, float]] = {}
    for metric_name in reference_metric_names:
        values = [
            run.references_metrics[metric_name]
            for run in runs
            if metric_name in run.references_metrics
        ]
        if not values:
            continue
        references_stats[metric_name] = _summarize_metric(values)

    return {
        "runs": len(runs),
        "failures": [run.run_index for run in runs if run.exit_code != 0],
        "total_elapsed_seconds": total_stats,
        "step_elapsed_seconds": step_stats,
        "run_profiles": [str(run.profile_path) for run in runs],
        "run_references_profiles": [
            str(run.references_profile_path)
            for run in runs
            if run.references_profile_path is not None
        ],
        "references_profile_metrics": references_stats,
    }


def prune_old_sessions(out_dir: Path, retention_sessions: int) -> list[str]:
    if retention_sessions < 1:
        return []
    sessions = sorted(
        (path for path in out_dir.iterdir() if path.is_dir() and path.name.startswith("session-")),
        key=lambda item: item.name,
    )
    if len(sessions) <= retention_sessions:
        return []
    removed: list[str] = []
    for stale in sessions[: len(sessions) - retention_sessions]:
        shutil.rmtree(stale)
        removed.append(stale.name)
    return removed


def profile_summary_from_scenario(name: str, summary: dict[str, object]) -> list[str]:
    lines = [f"[{name}]"]
    total_stats = summary.get("total_elapsed_seconds")
    if isinstance(total_stats, dict):
        lines.append(
            "  total_elapsed_seconds: "
            f"min={total_stats['min_seconds']:.3f}, "
            f"max={total_stats['max_seconds']:.3f}, "
            f"mean={total_stats['mean_seconds']:.3f}"
        )
    failures = summary.get("failures", [])
    lines.append(f"  failed_runs: {failures}")
    step_stats = summary.get("step_elapsed_seconds")
    if isinstance(step_stats, dict):
        for step_name in sorted(step_stats.keys()):
            values = step_stats[step_name]
            if not isinstance(values, dict):
                continue
            lines.append(
                f"  - {step_name}: min={values['min_seconds']:.3f}s, "
                f"max={values['max_seconds']:.3f}s, mean={values['mean_seconds']:.3f}s"
            )
    reference_stats = summary.get("references_profile_metrics")
    if isinstance(reference_stats, dict) and reference_stats:
        lines.append("  references_profile:")
        for metric_name in sorted(reference_stats.keys()):
            values = reference_stats[metric_name]
            if not isinstance(values, dict):
                continue
            lines.append(
                f"  - {metric_name}: min={values['min_seconds']:.6f}s, "
                f"max={values['max_seconds']:.6f}s, mean={values['mean_seconds']:.6f}s"
            )
    return lines


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    if args.retention_sessions < 1:
        raise SystemExit("--retention-sessions must be >= 1")

    scenarios = parse_scenarios(args.scenarios)
    source_repo_root = Path(args.repo_root).resolve()
    out_dir = (
        Path(args.out_dir).resolve() if args.out_dir else (source_repo_root / ".repo_mcp" / "perf")
    )
    fixtures_root = (
        Path(args.fixtures_root).resolve() if args.fixtures_root else (out_dir / "fixtures")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures_root.mkdir(parents=True, exist_ok=True)

    session_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    session_dir = out_dir / f"session-{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    scenario_repos: dict[str, str] = {}
    for scenario in scenarios:
        if scenario == "self":
            scenario_repos[scenario] = str(source_repo_root)
            continue
        fixture_repo = ensure_fixture_repo(
            fixtures_root=fixtures_root,
            scenario=scenario,
            source_repo_root=source_repo_root,
            rebuild=args.rebuild_fixtures,
        )
        scenario_repos[scenario] = str(fixture_repo)

    scenario_summaries: dict[str, dict[str, object]] = {}
    all_runs: list[BenchmarkRun] = []
    for scenario in scenarios:
        repo_root = Path(scenario_repos[scenario])
        scenario_out_dir = session_dir / scenario
        scenario_out_dir.mkdir(parents=True, exist_ok=True)
        runs = [
            run_one(
                scenario=scenario,
                repo_root=repo_root,
                scenario_out_dir=scenario_out_dir,
                run_index=index,
                response_timeout_seconds=args.response_timeout_seconds,
                profile_references=bool(args.profile_references),
            )
            for index in range(1, args.runs + 1)
        ]
        all_runs.extend(runs)
        scenario_summaries[scenario] = summarize_runs(runs)

    failures = sorted(f"{run.scenario}:{run.run_index}" for run in all_runs if run.exit_code != 0)
    summary = {
        "benchmark_version": 3,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "session_dir": str(session_dir),
        "protocol": {
            "scenarios": scenarios,
            "runs_per_scenario": args.runs,
            "response_timeout_seconds": args.response_timeout_seconds,
            "retention_sessions": args.retention_sessions,
            "profile_references": bool(args.profile_references),
            "scenario_repos": scenario_repos,
            "fixture_profiles": {
                name: {
                    "packages": profile.packages,
                    "modules_per_package": profile.modules_per_package,
                    "docs_files": profile.docs_files,
                    "helper_files_per_package": profile.helper_files_per_package,
                    "statements_per_module": profile.statements_per_module,
                }
                for name, profile in FIXTURE_PROFILES.items()
                if name in scenarios
            },
        },
        "scenarios": scenario_summaries,
        "failures": failures,
    }

    session_summary_path = session_dir / "benchmark_summary.json"
    latest_summary_path = out_dir / "benchmark_summary.json"
    session_summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    latest_summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    removed_sessions = prune_old_sessions(
        out_dir=out_dir, retention_sessions=args.retention_sessions
    )
    print("\n=== Benchmark Summary ===")
    for scenario in scenarios:
        for line in profile_summary_from_scenario(scenario, scenario_summaries[scenario]):
            print(line)
    print(f"failed_runs: {failures}")
    print(f"session_summary_json: {session_summary_path}")
    print(f"latest_summary_json: {latest_summary_path}")
    if removed_sessions:
        print(f"pruned_sessions: {removed_sessions}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
