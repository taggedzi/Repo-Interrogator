from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_bm25_basic_returns_relevant_ranked_hits(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "def run_alpha():\n    return 'alpha keyword alpha'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def run_beta():\n    return 'beta keyword'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    refreshed = server.handle_payload(
        {"id": "req-bm25-1", "method": "repo.refresh_index", "params": {}}
    )
    assert refreshed["ok"] is True

    response = server.handle_payload(
        {
            "id": "req-bm25-2",
            "method": "repo.search",
            "params": {"query": "alpha keyword", "mode": "bm25", "top_k": 2},
        }
    )
    assert response["ok"] is True
    hits = response["result"]["hits"]
    assert len(hits) == 2
    assert hits[0]["path"] == "src/alpha.py"
    assert hits[0]["score"] >= hits[1]["score"]
    assert "alpha" in hits[0]["matched_terms"]
    assert "keyword" in hits[0]["matched_terms"]
