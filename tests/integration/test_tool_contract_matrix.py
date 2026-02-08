from __future__ import annotations

from pathlib import Path

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

    requests = [
        ("repo.status", {}),
        ("repo.list_files", {"max_results": 10}),
        ("repo.open_file", {"path": "src/main.py", "start_line": 1, "end_line": 3}),
        ("repo.refresh_index", {"force": False}),
        ("repo.search", {"query": "search", "mode": "bm25", "top_k": 5}),
        ("repo.outline", {"path": "src/main.py"}),
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

    for idx, (method, params) in enumerate(requests):
        response = server.handle_payload(
            {"id": f"req-matrix-{idx}", "method": method, "params": params}
        )
        assert set(response.keys()) >= {"request_id", "ok", "result", "warnings", "blocked"}
        assert response["request_id"] == f"req-matrix-{idx}"
        assert isinstance(response["warnings"], list)
        if method == "repo.search":
            assert response["ok"] is True
            assert "hits" in response["result"]
        if method == "repo.outline":
            assert response["ok"] is True
            assert set(response["result"].keys()) == {"path", "language", "symbols"}
        if method == "repo.build_context_bundle":
            assert response["ok"] is True
            assert set(response["result"].keys()) == {
                "bundle_id",
                "prompt_fingerprint",
                "strategy",
                "budget",
                "totals",
                "selections",
                "citations",
                "audit",
            }
