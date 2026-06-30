from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_tie_break_uses_path_then_start_line(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    text = "keyword\n" * 40
    (tmp_path / "a" / "same.py").write_text(text, encoding="utf-8")
    (tmp_path / "b" / "same.py").write_text(text, encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-tie-1", "repo.refresh_index", {})

    first = call_tool(
        server, "req-tie-2", "repo.search", {"query": "keyword", "mode": "bm25", "top_k": 10}
    )
    second = call_tool(
        server, "req-tie-3", "repo.search", {"query": "keyword", "mode": "bm25", "top_k": 10}
    )

    first_hits = extract_result(first)["hits"]
    second_hits = extract_result(second)["hits"]
    assert [h["path"] for h in first_hits] == [h["path"] for h in second_hits]
    assert [h["start_line"] for h in first_hits] == [h["start_line"] for h in second_hits]
    assert first_hits[0]["path"] == "a/same.py"
    assert first_hits[1]["path"] == "b/same.py"
