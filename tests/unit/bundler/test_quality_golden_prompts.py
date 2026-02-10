from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.bundler import BundleBudget, BundleResult, build_context_bundle

RefPairs = dict[str, tuple[tuple[str, int], ...]]


def _search_hits_by_query() -> dict[str, list[dict[str, object]]]:
    return {
        "request id fallback routing": [
            {
                "path": "docs/notes.md",
                "start_line": 1,
                "end_line": 6,
                "score": 6.0,
                "matched_terms": ["request", "routing"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 286,
                "end_line": 291,
                "score": 5.2,
                "matched_terms": ["request", "fallback"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 252,
                "end_line": 286,
                "score": 4.8,
                "matched_terms": ["request", "id"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 124,
                "end_line": 250,
                "score": 2.9,
                "matched_terms": ["routing"],
            },
        ],
        "request": [
            {
                "path": "docs/notes.md",
                "start_line": 1,
                "end_line": 6,
                "score": 5.5,
                "matched_terms": ["request"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 252,
                "end_line": 286,
                "score": 4.6,
                "matched_terms": ["request"],
            },
        ],
        "fallback": [
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 286,
                "end_line": 291,
                "score": 5.1,
                "matched_terms": ["fallback"],
            },
            {
                "path": "docs/notes.md",
                "start_line": 1,
                "end_line": 6,
                "score": 4.4,
                "matched_terms": ["fallback"],
            },
        ],
        "routing": [
            {
                "path": "docs/notes.md",
                "start_line": 1,
                "end_line": 6,
                "score": 5.0,
                "matched_terms": ["routing"],
            }
        ],
        "path traversal blocked secrets": [
            {
                "path": "docs/security.md",
                "start_line": 1,
                "end_line": 10,
                "score": 6.1,
                "matched_terms": ["path", "blocked", "secrets"],
            },
            {
                "path": "src/repo_mcp/security/policy.py",
                "start_line": 30,
                "end_line": 70,
                "score": 5.7,
                "matched_terms": ["path", "blocked", "traversal"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 321,
                "end_line": 330,
                "score": 5.0,
                "matched_terms": ["blocked"],
            },
        ],
        "path": [
            {
                "path": "docs/security.md",
                "start_line": 1,
                "end_line": 10,
                "score": 5.6,
                "matched_terms": ["path"],
            },
            {
                "path": "src/repo_mcp/security/policy.py",
                "start_line": 30,
                "end_line": 70,
                "score": 5.5,
                "matched_terms": ["path"],
            },
        ],
        "traversal": [
            {
                "path": "src/repo_mcp/security/policy.py",
                "start_line": 30,
                "end_line": 70,
                "score": 5.8,
                "matched_terms": ["traversal"],
            }
        ],
        "blocked": [
            {
                "path": "src/repo_mcp/security/policy.py",
                "start_line": 30,
                "end_line": 70,
                "score": 5.9,
                "matched_terms": ["blocked"],
            },
            {
                "path": "src/repo_mcp/server.py",
                "start_line": 321,
                "end_line": 330,
                "score": 4.9,
                "matched_terms": ["blocked"],
            },
        ],
        "secrets": [
            {
                "path": "docs/security.md",
                "start_line": 1,
                "end_line": 10,
                "score": 5.7,
                "matched_terms": ["secrets"],
            }
        ],
    }


def _outline_for_path(path: str) -> list[dict[str, object]]:
    if path == "src/repo_mcp/server.py":
        return [
            {
                "kind": "method",
                "name": "StdioServer.parse_request",
                "start_line": 252,
                "end_line": 278,
            },
            {
                "kind": "method",
                "name": "StdioServer.extract_request_id",
                "start_line": 280,
                "end_line": 286,
            },
            {
                "kind": "method",
                "name": "StdioServer.next_request_id",
                "start_line": 288,
                "end_line": 291,
            },
            {
                "kind": "method",
                "name": "StdioServer.blocked_response",
                "start_line": 321,
                "end_line": 330,
            },
        ]
    if path == "src/repo_mcp/security/policy.py":
        return [
            {
                "kind": "function",
                "name": "blocked_path_traversal",
                "start_line": 30,
                "end_line": 70,
            }
        ]
    return []


def _reference_pairs(
    symbol_paths: dict[str, tuple[str, ...]],
) -> RefPairs:
    output: RefPairs = {}
    for symbol in sorted(symbol_paths.keys()):
        if symbol == "StdioServer.next_request_id":
            output[symbol] = (
                ("src/repo_mcp/server.py", 289),
                ("src/repo_mcp/server.py", 291),
            )
        elif symbol == "blocked_path_traversal":
            output[symbol] = (("src/repo_mcp/security/policy.py", 35),)
        else:
            output[symbol] = ()
    return output


def _build_bundle(prompt: str) -> BundleResult:
    query_hits = _search_hits_by_query()

    def search_fn(
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        _ = file_glob
        _ = path_prefix
        return query_hits.get(query, [])[:top_k]

    def read_lines_fn(path: str, start_line: int, end_line: int) -> list[str]:
        return [f"{path}:{line}" for line in range(start_line, end_line + 1)]

    return build_context_bundle(
        prompt=prompt,
        budget=BundleBudget(max_files=2, max_total_lines=80),
        search_fn=search_fn,
        read_lines_fn=read_lines_fn,
        outline_fn=_outline_for_path,
        reference_lookup_scoped_many_fn=_reference_pairs,
    )


def _quality_projection(bundle: BundleResult) -> dict[str, object]:
    return {
        "selected_paths": [item.path for item in bundle.selections],
        "selected_symbols": [
            item.why_selected.get("symbol_reference")
            for item in bundle.selections
            if item.why_selected.get("symbol_reference") is not None
        ],
        "top_ranked_paths": [item.path for item in bundle.audit.ranking_top_candidates[:5]],
        "top_ranked_selected": [item.selected for item in bundle.audit.ranking_top_candidates[:5]],
        "budget_enforcement_count": len(bundle.audit.budget_enforcement),
    }


def test_bundle_quality_hard_prompt_goldens_are_stable() -> None:
    expected = json.loads(
        Path("tests/fixtures/bundler/golden/context_bundle_quality_prompts.json").read_text(
            encoding="utf-8"
        )
    )

    prompts = [
        "request id fallback routing",
        "path traversal blocked secrets",
    ]
    first: dict[str, object] = {}
    second: dict[str, object] = {}
    for prompt in prompts:
        first[prompt] = _quality_projection(_build_bundle(prompt))
        second[prompt] = _quality_projection(_build_bundle(prompt))

    assert first == expected
    assert second == expected
    assert first == second
