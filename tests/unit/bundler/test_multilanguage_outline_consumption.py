from __future__ import annotations

from repo_mcp.bundler import BundleBudget, build_context_bundle


def test_bundle_aligns_hit_ranges_to_outline_symbols_when_available() -> None:
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
                "path": "src/mod.ts",
                "start_line": 10,
                "end_line": 20,
                "score": 2.0,
                "matched_terms": ["build", "service"],
            }
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        assert path == "src/mod.ts"
        return [
            {
                "kind": "class",
                "name": "Service",
                "start_line": 2,
                "end_line": 30,
            },
            {
                "kind": "method",
                "name": "Service.build",
                "start_line": 12,
                "end_line": 16,
            },
        ]

    bundle = build_context_bundle(
        prompt="build service",
        budget=BundleBudget(max_files=2, max_total_lines=50),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
    )

    assert len(bundle.selections) == 1
    selection = bundle.selections[0]
    assert selection.path == "src/mod.ts"
    assert selection.start_line == 12
    assert selection.end_line == 16
    assert selection.why_selected["symbol_reference"] == "Service.build"
    assert "aligned_symbol" in selection.why_selected["matched_signals"]
    assert "aligned_symbol=Service.build" in selection.rationale


def test_bundle_falls_back_to_raw_hit_ranges_when_no_symbols_present() -> None:
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
                "path": "src/mod.go",
                "start_line": 3,
                "end_line": 7,
                "score": 1.2,
                "matched_terms": ["build"],
            }
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        _ = path
        return []

    bundle = build_context_bundle(
        prompt="build",
        budget=BundleBudget(max_files=2, max_total_lines=50),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
    )

    assert len(bundle.selections) == 1
    selection = bundle.selections[0]
    assert selection.start_line == 3
    assert selection.end_line == 7
    assert selection.why_selected["symbol_reference"] is None
    assert "aligned_symbol" not in selection.why_selected["matched_signals"]
    assert "aligned_symbol=" not in selection.rationale
