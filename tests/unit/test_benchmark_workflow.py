from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_benchmark_module():
    script_path = Path("scripts/benchmark_workflow.py").resolve()
    spec = importlib.util.spec_from_file_location("benchmark_workflow", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_parse_scenarios_dedupes_and_preserves_order() -> None:
    module = _load_benchmark_module()
    parsed = module.parse_scenarios("self, medium, self,large")
    assert parsed == ["self", "medium", "large"]


def test_write_fixture_repo_creates_expected_shape(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    fixture_root = tmp_path / "fixtures" / "medium"
    profile = module.FixtureProfile(
        packages=2,
        modules_per_package=3,
        docs_files=2,
        helper_files_per_package=1,
        statements_per_module=4,
    )
    source_repo_root = Path(".").resolve()
    module.write_fixture_repo(
        fixture_root=fixture_root,
        profile=profile,
        profile_name="medium",
        source_repo_root=source_repo_root,
    )

    assert (fixture_root / "src" / "repo_mcp" / "server.py").exists()
    generated_modules = sorted((fixture_root / "src").glob("generated_pkg_*/module_*.py"))
    generated_helpers = sorted((fixture_root / "src").glob("generated_pkg_*/helper_*.py"))
    generated_docs = sorted((fixture_root / "docs").glob("scenario_medium_*.md"))
    assert len(generated_modules) == 6
    assert len(generated_helpers) == 2
    assert len(generated_docs) == 2

    marker_path = fixture_root / ".fixture_profile.json"
    assert marker_path.exists()
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker["profile"]["modules_per_package"] == 3


def test_summarize_runs_includes_expected_fields(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    run = module.BenchmarkRun(
        scenario="self",
        run_index=1,
        exit_code=0,
        elapsed_seconds=10.0,
        profile_path=tmp_path / "run_01.json",
        references_profile_path=None,
        bundler_profile_path=None,
        total_elapsed_seconds=9.5,
        steps={"repo.refresh_index": 4.0, "repo.build_context_bundle": 5.0},
        references_metrics={},
        bundler_metrics={},
    )
    summary = module.summarize_runs([run])
    assert summary["runs"] == 1
    assert summary["failures"] == []
    totals = summary["total_elapsed_seconds"]
    assert isinstance(totals, dict)
    assert totals["mean_seconds"] == 9.5
    steps = summary["step_elapsed_seconds"]
    assert isinstance(steps, dict)
    assert "repo.refresh_index" in steps


def test_prune_old_sessions_keeps_newest(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    for name in [
        "session-20260101T010101Z",
        "session-20260102T010101Z",
        "session-20260103T010101Z",
    ]:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    removed = module.prune_old_sessions(out_dir=tmp_path, retention_sessions=2)
    assert removed == ["session-20260101T010101Z"]
    remaining = sorted(path.name for path in tmp_path.iterdir() if path.is_dir())
    assert remaining == ["session-20260102T010101Z", "session-20260103T010101Z"]


def test_summarize_reference_profile_extracts_targeted_metrics(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    profile_path = tmp_path / "references.jsonl"
    profile_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "candidate_discovery": {
                            "candidate_discovery_seconds": 1.2,
                            "discover_files_seconds": 0.2,
                            "policy_seconds": 0.3,
                            "read_files_seconds": 0.7,
                        },
                        "adapter_resolution": {
                            "adapter_select_seconds": 0.04,
                            "resolver_seconds": 0.6,
                            "normalize_sort_seconds": 0.01,
                        },
                    }
                ),
                json.dumps(
                    {
                        "candidate_discovery": {
                            "candidate_discovery_seconds": 1.0,
                            "discover_files_seconds": 0.1,
                            "policy_seconds": 0.2,
                            "read_files_seconds": 0.7,
                        },
                        "adapter_resolution": {
                            "adapter_select_seconds": 0.05,
                            "resolver_seconds": 0.5,
                            "normalize_sort_seconds": 0.02,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = module.summarize_reference_profile(profile_path)
    assert summary["candidate_discovery_seconds_mean"] == 1.1
    assert summary["adapter_select_seconds_mean"] == 0.045


def test_summarize_bundler_profile_extracts_targeted_metrics(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    profile_path = tmp_path / "bundler.jsonl"
    profile_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "dedupe_seconds": 0.02,
                        "ranking_seconds": 0.3,
                        "budget_enforcement_seconds": 0.05,
                        "total_build_seconds": 0.6,
                    }
                ),
                json.dumps(
                    {
                        "dedupe_seconds": 0.04,
                        "ranking_seconds": 0.5,
                        "budget_enforcement_seconds": 0.07,
                        "total_build_seconds": 0.8,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = module.summarize_bundler_profile(profile_path)
    assert summary["dedupe_seconds_mean"] == 0.03
    assert summary["budget_enforcement_seconds_mean"] == 0.060000000000000005


def test_scenario_mean_metrics_extracts_expected_keys() -> None:
    module = _load_benchmark_module()
    summary = {
        "total_elapsed_seconds": {"mean_seconds": 2.5},
        "step_elapsed_seconds": {
            "repo.refresh_index": {"mean_seconds": 1.2},
            "repo.build_context_bundle": {"mean_seconds": 1.3},
        },
        "references_profile_metrics": {"candidate_discovery_seconds_mean": {"mean_seconds": 0.4}},
        "bundler_profile_metrics": {"ranking_seconds_mean": {"mean_seconds": 0.2}},
    }
    metrics = module.scenario_mean_metrics(summary)
    assert metrics["total_elapsed_seconds"] == 2.5
    assert metrics["step:repo.refresh_index"] == 1.2
    assert metrics["references:candidate_discovery_seconds_mean"] == 0.4
    assert metrics["bundler:ranking_seconds_mean"] == 0.2


def test_evaluate_regression_guardrails_detects_drift() -> None:
    module = _load_benchmark_module()
    current = {
        "self": {
            "total_elapsed_seconds": {"mean_seconds": 12.0},
            "step_elapsed_seconds": {"repo.refresh_index": {"mean_seconds": 6.0}},
            "references_profile_metrics": {},
            "bundler_profile_metrics": {},
        }
    }
    baseline = {
        "self": {
            "total_elapsed_seconds": {"mean_seconds": 10.0},
            "step_elapsed_seconds": {"repo.refresh_index": {"mean_seconds": 4.0}},
            "references_profile_metrics": {},
            "bundler_profile_metrics": {},
        }
    }
    warnings = module.evaluate_regression_guardrails(
        current_summaries=current,
        baseline_summaries=baseline,
        threshold_percent=15.0,
    )
    assert len(warnings) == 2
    assert warnings[0].scenario == "self"
    assert warnings[0].delta_percent > 15.0


def test_evaluate_regression_guardrails_ignores_below_threshold() -> None:
    module = _load_benchmark_module()
    current = {
        "self": {
            "total_elapsed_seconds": {"mean_seconds": 10.5},
            "step_elapsed_seconds": {},
            "references_profile_metrics": {},
            "bundler_profile_metrics": {},
        }
    }
    baseline = {
        "self": {
            "total_elapsed_seconds": {"mean_seconds": 10.0},
            "step_elapsed_seconds": {},
            "references_profile_metrics": {},
            "bundler_profile_metrics": {},
        }
    }
    warnings = module.evaluate_regression_guardrails(
        current_summaries=current,
        baseline_summaries=baseline,
        threshold_percent=10.0,
    )
    assert warnings == []


def test_load_baseline_summaries_reads_scenarios(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "benchmark_version": 4,
                "scenarios": {
                    "self": {
                        "total_elapsed_seconds": {"mean_seconds": 5.0},
                        "step_elapsed_seconds": {},
                        "references_profile_metrics": {},
                        "bundler_profile_metrics": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = module.load_baseline_summaries(baseline_path)
    assert "self" in loaded


def test_load_baseline_summaries_requires_scenarios(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    baseline_path = tmp_path / "bad_baseline.json"
    baseline_path.write_text(json.dumps({"benchmark_version": 4}), encoding="utf-8")
    try:
        module.load_baseline_summaries(baseline_path)
    except ValueError as exc:
        assert "missing 'scenarios'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing scenarios")
