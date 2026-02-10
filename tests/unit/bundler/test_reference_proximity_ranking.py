from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_bundle_ranking_uses_reference_proximity_across_files() -> None:
    def search_fn(
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        _ = query
        _ = top_k
        _ = file_glob
        _ = path_prefix
        return [
            {
                "path": "src/high_score.py",
                "start_line": 10,
                "end_line": 12,
                "score": 5.0,
                "matched_terms": ["run"],
            },
            {
                "path": "src/low_score.py",
                "start_line": 30,
                "end_line": 32,
                "score": 1.0,
                "matched_terms": ["service", "run"],
            },
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        if path == "src/high_score.py":
            return [
                {"kind": "function", "name": "Helper.run", "start_line": 10, "end_line": 12},
            ]
        if path == "src/low_score.py":
            return [
                {"kind": "method", "name": "Service.run", "start_line": 30, "end_line": 32},
            ]
        return []

    def reference_lookup_fn(symbol: str) -> list[dict[str, object]]:
        if symbol == "Service.run":
            return [
                {"path": "src/low_score.py", "line": 31},
                {"path": "src/other.py", "line": 12},
            ]
        return []

    bundle = build_context_bundle(
        prompt="service run",
        budget=BundleBudget(max_files=5, max_total_lines=50),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
        reference_lookup_fn=reference_lookup_fn,
    )

    assert len(bundle.selections) == 2
    assert [item.path for item in bundle.selections] == ["src/low_score.py", "src/high_score.py"]
    first = bundle.selections[0]
    assert "reference_proximity" in first.why_selected["matched_signals"]
    score_components = first.why_selected["score_components"]
    assert score_components["reference_count_in_range"] == 1
    assert score_components["min_definition_distance"] == 0
    assert bundle.audit.ranking_candidate_count == 2
    assert bundle.audit.ranking_reference_proximity_count == 1
    assert bundle.audit.ranking_top_candidates[0].selected is True
