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
        total_elapsed_seconds=9.5,
        steps={"repo.refresh_index": 4.0, "repo.build_context_bundle": 5.0},
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
