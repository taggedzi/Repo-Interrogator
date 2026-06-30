from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_tool_contract_matrix_for_required_v1_tools(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "class Main:\n    def run(self) -> int:\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text("search term\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    # Seed index for search/bundle
    call_tool(server, "req-matrix-seed", "repo.refresh_index", {"force": False})

    tool_calls: list[tuple[str, dict[str, object]]] = [
        ("repo.status", {}),
        ("repo.list_files", {"max_results": 10}),
        ("repo.open_file", {"path": "src/main.py", "start_line": 1, "end_line": 3}),
        ("repo.refresh_index", {"force": False}),
        ("repo.search", {"query": "search", "mode": "bm25", "top_k": 5}),
        ("repo.outline", {"path": "src/main.py"}),
        ("repo.references", {"symbol": "Main.run", "top_k": 5}),
        (
            "repo.build_context_bundle",
            {
                "prompt": "main run search",
                "budget": {"max_files": 2, "max_total_lines": 20},
                "strategy": "hybrid",
                "include_tests": True,
            },
        ),
        ("repo.audit_log", {"limit": 20}),
    ]

    for idx, (tool_name, arguments) in enumerate(tool_calls):
        response = call_tool(server, f"req-matrix-{idx}", tool_name, arguments)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == f"req-matrix-{idx}"
        assert not is_tool_error(response), f"{tool_name} returned isError: {response}"
        result = extract_result(response)

        if tool_name == "repo.search":
            assert "hits" in result
        if tool_name == "repo.outline":
            assert set(result.keys()) == {"path", "language", "symbols"}
            assert result["symbols"]
            assert set(result["symbols"][0].keys()) == {
                "kind",
                "name",
                "signature",
                "start_line",
                "end_line",
                "doc",
                "parent_symbol",
                "scope_kind",
                "is_conditional",
                "decl_context",
            }
        if tool_name == "repo.build_context_bundle":
            assert set(result.keys()) == {
                "bundle_id",
                "prompt_fingerprint",
                "strategy",
                "budget",
                "totals",
                "selections",
                "citations",
                "audit",
            }
            selections = result["selections"]
            assert isinstance(selections, list)
            if selections:
                first = selections[0]
                assert set(first.keys()) == {
                    "path",
                    "start_line",
                    "end_line",
                    "excerpt",
                    "why_selected",
                    "rationale",
                    "score",
                    "source_query",
                }
        if tool_name == "repo.references":
            assert set(result.keys()) == {
                "symbol",
                "references",
                "truncated",
                "total_candidates",
            }
