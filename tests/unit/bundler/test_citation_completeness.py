from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_bundle_citations_and_rationales_are_complete() -> None:
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
                "path": "pkg/core.py",
                "start_line": 5,
                "end_line": 7,
                "score": 1.7,
                "matched_terms": ["core", "logic"],
            }
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path} line {idx}" for idx in range(start_line, end_line + 1)]

    bundle = build_context_bundle(
        prompt="core logic",
        budget=BundleBudget(max_files=3, max_total_lines=50),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
    )

    assert len(bundle.selections) == 1
    selection = bundle.selections[0]
    citation = bundle.citations[0]

    assert selection.path == "pkg/core.py"
    assert selection.start_line == 5
    assert selection.end_line == 7
    assert selection.rationale
    assert "matched_terms" in selection.rationale
    assert citation.path == selection.path
    assert citation.start_line == selection.start_line
    assert citation.end_line == selection.end_line
    assert citation.selection_index == 0
