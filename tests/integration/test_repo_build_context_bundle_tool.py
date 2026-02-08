from __future__ import annotations

import json
from pathlib import Path

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
    refreshed = server.handle_payload(
        {"id": "req-bundle-1", "method": "repo.refresh_index", "params": {}}
    )
    assert refreshed["ok"] is True

    response = server.handle_payload(
        {
            "id": "req-bundle-2",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "parser tokens",
                "budget": {"max_files": 2, "max_total_lines": 10},
                "strategy": "hybrid",
                "include_tests": True,
            },
        }
    )
    assert response["ok"] is True
    assert response["blocked"] is False
    result = response["result"]
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
    if result["selections"]:
        first = result["selections"][0]
        assert set(first.keys()) == {
            "path",
            "start_line",
            "end_line",
            "excerpt",
            "rationale",
            "score",
            "source_query",
        }

    json_artifact = tmp_path / ".repo_mcp" / "last_bundle.json"
    md_artifact = tmp_path / ".repo_mcp" / "last_bundle.md"
    assert json_artifact.exists()
    assert md_artifact.exists()
    loaded = json.loads(json_artifact.read_text(encoding="utf-8"))
    assert loaded["bundle_id"] == result["bundle_id"]
