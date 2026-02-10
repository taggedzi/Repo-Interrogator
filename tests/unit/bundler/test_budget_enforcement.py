from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_bundle_budget_enforcement_limits_files_and_lines() -> None:
    hits = [
        {
            "path": "src/a.py",
            "start_line": 1,
            "end_line": 4,
            "score": 2.0,
            "matched_terms": ["alpha"],
        },
        {
            "path": "src/b.py",
            "start_line": 1,
            "end_line": 4,
            "score": 1.5,
            "matched_terms": ["beta"],
        },
        {
            "path": "src/c.py",
            "start_line": 1,
            "end_line": 4,
            "score": 1.0,
            "matched_terms": ["gamma"],
        },
    ]

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
        return hits

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        _ = path
        return [f"line-{idx}" for idx in range(start_line, end_line + 1)]

    bundle = build_context_bundle(
        prompt="alpha beta gamma",
        budget=BundleBudget(max_files=2, max_total_lines=8),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
    )

    assert bundle.totals.selected_files == 2
    assert bundle.totals.selected_lines == 8
    assert bundle.totals.truncated is True
    assert len(bundle.selections) == 2
    assert [s.path for s in bundle.selections] == ["src/a.py", "src/b.py"]
    summary = bundle.audit.selection_debug.why_not_selected_summary
    assert summary.total_skipped_candidates == 1
    assert summary.reason_counts == {
        "file_budget": 1,
        "line_budget": 0,
        "zero_lines": 0,
        "other": 0,
    }
    assert len(summary.top_skipped) == 1
    assert summary.top_skipped[0].reason == "file_budget"
    assert summary.top_skipped[0].path == "src/c.py"
