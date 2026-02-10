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


def test_ranking_prefers_batch_reference_lookup_when_available() -> None:
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
                "path": "src/service.py",
                "start_line": 10,
                "end_line": 12,
                "score": 2.0,
                "matched_terms": ["service", "run"],
            },
            {
                "path": "src/helper.py",
                "start_line": 20,
                "end_line": 22,
                "score": 1.0,
                "matched_terms": ["helper", "run"],
            },
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        if path == "src/service.py":
            return [{"kind": "method", "name": "Service.run", "start_line": 10, "end_line": 12}]
        if path == "src/helper.py":
            return [{"kind": "function", "name": "Helper.run", "start_line": 20, "end_line": 22}]
        return []

    single_calls = 0
    batch_calls = 0

    def reference_lookup_fn(symbol: str) -> list[dict[str, object]]:
        nonlocal single_calls
        _ = symbol
        single_calls += 1
        return []

    def reference_lookup_many_fn(symbols: list[str]) -> dict[str, list[dict[str, object]]]:
        nonlocal batch_calls
        batch_calls += 1
        return {
            symbol: [{"path": "src/service.py", "line": 11}] if symbol == "Service.run" else []
            for symbol in symbols
        }

    bundle = build_context_bundle(
        prompt="service run",
        budget=BundleBudget(max_files=3, max_total_lines=30),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
        reference_lookup_fn=reference_lookup_fn,
        reference_lookup_many_fn=reference_lookup_many_fn,
    )

    assert bundle.selections
    assert batch_calls == 1
    assert single_calls == 0


def test_ranking_accepts_compact_reference_pairs_from_batch_lookup() -> None:
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
                "path": "src/service.py",
                "start_line": 10,
                "end_line": 12,
                "score": 1.0,
                "matched_terms": ["service", "run"],
            },
            {
                "path": "src/other.py",
                "start_line": 2,
                "end_line": 4,
                "score": 2.0,
                "matched_terms": ["service", "run"],
            },
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        if path == "src/service.py":
            return [{"kind": "method", "name": "Service.run", "start_line": 10, "end_line": 12}]
        if path == "src/other.py":
            return [{"kind": "function", "name": "Other.run", "start_line": 2, "end_line": 4}]
        return []

    def reference_lookup_many_fn(
        symbols: list[str],
    ) -> dict[str, tuple[tuple[str, int], ...]]:
        return {
            symbol: (("src/service.py", 11),) if symbol == "Service.run" else ()
            for symbol in symbols
        }

    bundle = build_context_bundle(
        prompt="service run",
        budget=BundleBudget(max_files=2, max_total_lines=20),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
        reference_lookup_many_fn=reference_lookup_many_fn,
    )

    assert bundle.selections
    assert bundle.selections[0].path == "src/service.py"


def test_ranking_prefers_scoped_batch_reference_lookup_when_available() -> None:
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
                "path": "src/service.py",
                "start_line": 10,
                "end_line": 12,
                "score": 2.0,
                "matched_terms": ["service", "run"],
            },
            {
                "path": "src/other.py",
                "start_line": 4,
                "end_line": 6,
                "score": 1.0,
                "matched_terms": ["service", "run"],
            },
        ]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    def outline_fn(path: str) -> list[dict[str, object]]:
        if path == "src/service.py":
            return [{"kind": "method", "name": "Service.run", "start_line": 10, "end_line": 12}]
        if path == "src/other.py":
            return [{"kind": "method", "name": "Service.run", "start_line": 4, "end_line": 6}]
        return []

    single_calls = 0
    batch_calls = 0
    scoped_calls = 0
    captured_payload: dict[str, tuple[str, ...]] = {}

    def reference_lookup_fn(symbol: str) -> list[dict[str, object]]:
        nonlocal single_calls
        _ = symbol
        single_calls += 1
        return []

    def reference_lookup_many_fn(symbols: list[str]) -> dict[str, list[dict[str, object]]]:
        nonlocal batch_calls
        _ = symbols
        batch_calls += 1
        return {}

    def reference_lookup_scoped_many_fn(
        symbol_paths: dict[str, tuple[str, ...]],
    ) -> dict[str, tuple[tuple[str, int], ...]]:
        nonlocal scoped_calls, captured_payload
        scoped_calls += 1
        captured_payload = symbol_paths
        return {"Service.run": (("src/service.py", 11),)}

    bundle = build_context_bundle(
        prompt="service run",
        budget=BundleBudget(max_files=3, max_total_lines=30),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=outline_fn,
        reference_lookup_fn=reference_lookup_fn,
        reference_lookup_many_fn=reference_lookup_many_fn,
        reference_lookup_scoped_many_fn=reference_lookup_scoped_many_fn,
    )

    assert bundle.selections
    assert scoped_calls == 1
    assert batch_calls == 0
    assert single_calls == 0
    assert captured_payload == {"Service.run": ("src/other.py", "src/service.py")}
