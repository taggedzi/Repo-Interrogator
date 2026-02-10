from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle
from repo_mcp.bundler.engine import _query_top_k


def test_query_top_k_scales_keyword_queries_deterministically() -> None:
    assert _query_top_k(query_index=0, base_top_k=50) == 50
    assert _query_top_k(query_index=1, base_top_k=50) == 12
    assert _query_top_k(query_index=2, base_top_k=20) == 5
    assert _query_top_k(query_index=3, base_top_k=4) == 4


def test_build_context_bundle_uses_lower_top_k_for_keyword_queries() -> None:
    calls: list[tuple[str, int]] = []

    def search_fn(
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        _ = file_glob
        _ = path_prefix
        calls.append((query, top_k))
        return []

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        _ = path
        _ = start_line
        _ = end_line
        return []

    build_context_bundle(
        prompt="server request handling and search flow",
        budget=BundleBudget(max_files=2, max_total_lines=80),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        top_k_per_query=50,
    )

    assert calls
    first_query, first_top_k = calls[0]
    assert first_query == "server request handling and search flow"
    assert first_top_k == 50
    for _, keyword_top_k in calls[1:]:
        assert keyword_top_k == 12
