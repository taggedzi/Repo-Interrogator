from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from repo_mcp.adapters import PythonAstAdapter


def test_python_reference_output_matches_golden_snapshot_and_is_stable() -> None:
    files = [
        (
            "src\\b.py",
            """
from service import Service

def use_b() -> int:
    svc = Service()
    return svc.run()
""",
        ),
        (
            "src/a.py",
            """
from service import Service

def use_a() -> int:
    svc = Service()
    return svc.run()
""",
        ),
    ]
    expected = json.loads(
        Path("tests/fixtures/adapters/golden/python_references.json").read_text(encoding="utf-8")
    )
    adapter = PythonAstAdapter()

    first = {
        "symbol": "Service.run",
        "references": [
            asdict(item) for item in adapter.references_for_symbol("Service.run", files)
        ],
    }
    second = {
        "symbol": "Service.run",
        "references": [
            asdict(item) for item in adapter.references_for_symbol("Service.run", files)
        ],
    }

    assert first == expected
    assert second == expected
    assert first == second
