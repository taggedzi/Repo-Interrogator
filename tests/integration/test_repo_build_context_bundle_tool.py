from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_repo_build_context_bundle_tool_returns_structured_payload(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "def alpha_parser():\n    return 'parse alpha tokens'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def beta_parser():\n    return 'parse beta tokens'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-bundle-1", "repo.refresh_index", {})

    result = extract_result(
        call_tool(
            server,
            "req-bundle-2",
            "repo.build_context_bundle",
            {
                "prompt": "parser tokens",
                "budget": {"max_files": 2, "max_total_lines": 10},
                "strategy": "hybrid",
                "include_tests": True,
            },
        )
    )

    assert result["strategy"] == "hybrid"
    assert result["budget"] == {"max_files": 2, "max_total_lines": 10}
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
    assert isinstance(result["selections"], list)
    assert isinstance(result["citations"], list)
    assert set(result["audit"].keys()) == {
        "search_queries",
        "dedupe_counts",
        "budget_enforcement",
        "ranking_debug",
        "selection_debug",
    }
