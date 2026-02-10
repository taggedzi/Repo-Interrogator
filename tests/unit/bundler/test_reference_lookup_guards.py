from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_ranking_skips_reference_lookup_for_unaligned_hits() -> None:
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
                "path": "docs/readme.md",
                "start_line": 1,
                "end_line": 3,
                "score": 1.0,
                "matched_terms": ["server"],
            }
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    lookup_calls = 0

    def reference_lookup_fn(symbol: str) -> list[dict[str, object]]:
        nonlocal lookup_calls
        _ = symbol
        lookup_calls += 1
        return []

    bundle = build_context_bundle(
        prompt="server",
        budget=BundleBudget(max_files=2, max_total_lines=20),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=lambda path: [],
        reference_lookup_fn=reference_lookup_fn,
    )

    assert bundle.selections
    assert lookup_calls == 0
