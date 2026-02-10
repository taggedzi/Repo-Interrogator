from __future__ import annotations

import cProfile
import importlib.util
import sys
from pathlib import Path


def _load_validate_module():
    script_path = Path("scripts/validate_workflow.py").resolve()
    spec = importlib.util.spec_from_file_location("validate_workflow", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def _busy_work() -> int:
    total = 0
    for value in range(2000):
        total += value * value
    return total


def test_summarize_cprofile_returns_ranked_lines(tmp_path: Path) -> None:
    module = _load_validate_module()
    output_path = tmp_path / "server_profile.pstats"
    profiler = cProfile.Profile()
    profiler.enable()
    _busy_work()
    profiler.disable()
    profiler.dump_stats(str(output_path))

    lines = module.summarize_cprofile(output_path, top=5)
    assert lines
    assert lines[0].startswith("Top ")
    assert any("_busy_work" in line for line in lines[1:])
