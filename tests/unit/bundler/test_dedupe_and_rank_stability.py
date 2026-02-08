from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_bundle_dedupe_and_rank_stability() -> None:
    query_hits = {
        "parser": [
            {
                "path": "src/a.py",
                "start_line": 10,
                "end_line": 20,
                "score": 1.0,
                "matched_terms": ["parser"],
            },
            {
                "path": "src/b.py",
                "start_line": 1,
                "end_line": 5,
                "score": 0.8,
                "matched_terms": ["parser"],
            },
        ],
        "prompt full": [
            {
                "path": "src/a.py",
                "start_line": 10,
                "end_line": 20,
                "score": 2.0,
                "matched_terms": ["prompt"],
            },
            {
                "path": "src/c.py",
                "start_line": 1,
                "end_line": 3,
                "score": 0.5,
                "matched_terms": ["prompt"],
            },
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
        if query in {"prompt full", "prompt full parser", "full"}:
            return query_hits["prompt full"]
        if query == "prompt":
            return [
                {
                    "path": "src/a.py",
                    "start_line": 10,
                    "end_line": 20,
                    "score": 1.9,
                    "matched_terms": ["prompt"],
                }
            ]
        return query_hits.get(query, [])

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    first = build_context_bundle(
        prompt="prompt full parser",
        budget=BundleBudget(max_files=10, max_total_lines=100),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
    )
    second = build_context_bundle(
        prompt="prompt full parser",
        budget=BundleBudget(max_files=10, max_total_lines=100),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
    )

    assert first.audit.dedupe_before > first.audit.dedupe_after
    assert [s.path for s in first.selections] == [s.path for s in second.selections]
    assert [s.start_line for s in first.selections] == [s.start_line for s in second.selections]
    assert first.selections[0].path == "src/a.py"
    assert first.selections[0].score == 2.0
