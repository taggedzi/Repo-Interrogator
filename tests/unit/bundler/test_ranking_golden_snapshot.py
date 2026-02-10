from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from repo_mcp.bundler import BundleBudget, BundleResult, build_context_bundle


def _build_fixture_bundle() -> BundleResult:
    query_hits = {
        "service run parser": [
            {
                "path": "src/service.py",
                "start_line": 1,
                "end_line": 12,
                "score": 2.5,
                "matched_terms": ["service", "run"],
            },
            {
                "path": "src/app.py",
                "start_line": 10,
                "end_line": 20,
                "score": 1.6,
                "matched_terms": ["parser"],
            },
        ],
        "service": [
            {
                "path": "src/service.py",
                "start_line": 1,
                "end_line": 12,
                "score": 2.4,
                "matched_terms": ["service"],
            }
        ],
        "run": [
            {
                "path": "src/app.py",
                "start_line": 10,
                "end_line": 20,
                "score": 1.5,
                "matched_terms": ["run"],
            }
        ],
        "parser": [
            {
                "path": "src/utils.py",
                "start_line": 3,
                "end_line": 8,
                "score": 1.2,
                "matched_terms": ["parser"],
            }
        ],
    }

    def search_fn(
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        _ = top_k
        _ = file_glob
        _ = path_prefix
        return query_hits.get(query, [])

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        if path == "src/service.py":
            return [
                {"kind": "class", "name": "Service", "start_line": 1, "end_line": 12},
                {"kind": "method", "name": "Service.run", "start_line": 4, "end_line": 7},
            ]
        if path == "src/app.py":
            return [
                {"kind": "function", "name": "use_service", "start_line": 11, "end_line": 18},
            ]
        return []

    return build_context_bundle(
        prompt="service run parser",
        budget=BundleBudget(max_files=2, max_total_lines=16),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
    )


def _to_payload(bundle: BundleResult) -> dict[str, object]:
    return {
        "bundle_id": bundle.bundle_id,
        "prompt_fingerprint": bundle.prompt_fingerprint,
        "strategy": bundle.strategy,
        "budget": asdict(bundle.budget),
        "totals": asdict(bundle.totals),
        "selections": [asdict(item) for item in bundle.selections],
        "citations": [asdict(item) for item in bundle.citations],
        "audit": {
            "search_queries": list(bundle.audit.search_queries),
            "dedupe_counts": {
                "before": bundle.audit.dedupe_before,
                "after": bundle.audit.dedupe_after,
            },
            "budget_enforcement": list(bundle.audit.budget_enforcement),
            "ranking_debug": {
                "candidate_count": bundle.audit.ranking_candidate_count,
                "definition_match_count": bundle.audit.ranking_definition_match_count,
                "reference_proximity_count": bundle.audit.ranking_reference_proximity_count,
                "top_candidates": [asdict(item) for item in bundle.audit.ranking_top_candidates],
            },
            "selection_debug": {
                "why_not_selected_summary": {
                    "total_skipped_candidates": (
                        bundle.audit.selection_debug.why_not_selected_summary.total_skipped_candidates
                    ),
                    "reason_counts": (
                        bundle.audit.selection_debug.why_not_selected_summary.reason_counts
                    ),
                    "top_skipped": [
                        asdict(item)
                        for item in (
                            bundle.audit.selection_debug.why_not_selected_summary.top_skipped
                        )
                    ],
                }
            },
        },
    }


def test_bundle_ranking_output_matches_golden_snapshot_and_is_stable() -> None:
    expected = json.loads(
        Path("tests/fixtures/bundler/golden/context_bundle_ranking.json").read_text(
            encoding="utf-8"
        )
    )

    first = _to_payload(_build_fixture_bundle())
    second = _to_payload(_build_fixture_bundle())

    assert first == expected
    assert second == expected
    assert first == second
