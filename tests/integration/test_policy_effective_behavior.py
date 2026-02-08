from __future__ import annotations

from pathlib import Path

from repo_mcp.config import CliOverrides
from repo_mcp.server import create_server


def test_effective_policy_limits_and_denylist_behavior(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_file_bytes = 1024",
                "max_open_lines = 10",
                "max_total_bytes_per_response = 2048",
                "max_search_hits = 5",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("keyword\n", encoding="utf-8")

    server = create_server(
        repo_root=str(tmp_path),
        cli_overrides=CliOverrides(max_search_hits=4),
    )

    status = server.handle_payload({"id": "req-pol-1", "method": "repo.status", "params": {}})
    assert status["ok"] is True
    assert status["result"]["limits_summary"]["max_search_hits"] == 4

    blocked = server.handle_payload(
        {
            "id": "req-pol-2",
            "method": "repo.open_file",
            "params": {"path": ".env", "start_line": 1, "end_line": 1},
        }
    )
    assert blocked["blocked"] is True
    assert blocked["error"]["code"] == "PATH_BLOCKED"

    server.handle_payload({"id": "req-pol-3", "method": "repo.refresh_index", "params": {}})
    search_blocked = server.handle_payload(
        {
            "id": "req-pol-4",
            "method": "repo.search",
            "params": {"query": "keyword", "mode": "bm25", "top_k": 10},
        }
    )
    assert search_blocked["blocked"] is True
    assert search_blocked["error"]["code"] == "PATH_BLOCKED"
