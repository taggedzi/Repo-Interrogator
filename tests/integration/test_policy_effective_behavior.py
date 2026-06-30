from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

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

    status = call_tool(server, "req-pol-1", "repo.status", {})
    assert not is_tool_error(status)
    assert extract_result(status)["limits_summary"]["max_search_hits"] == 4

    blocked = call_tool(
        server,
        "req-pol-2",
        "repo.open_file",
        {"path": ".env", "start_line": 1, "end_line": 1},
    )
    assert is_tool_error(blocked)

    call_tool(server, "req-pol-3", "repo.refresh_index", {})
    search_blocked = call_tool(
        server,
        "req-pol-4",
        "repo.search",
        {"query": "keyword", "mode": "bm25", "top_k": 10},
    )
    assert is_tool_error(search_blocked)
