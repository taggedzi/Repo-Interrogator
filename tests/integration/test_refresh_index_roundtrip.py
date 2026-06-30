from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server
from tests.helpers import call_tool, extract_result, is_tool_error


def test_refresh_index_roundtrip_and_status_snapshot(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    first = call_tool(server, "req-r1", "repo.refresh_index", {"force": False})
    assert not is_tool_error(first)
    assert extract_result(first)["added"] == 2
    assert extract_result(first)["updated"] == 0
    assert extract_result(first)["removed"] == 0
    assert isinstance(extract_result(first)["timestamp"], str)

    status = call_tool(server, "req-r2", "repo.status", {})
    assert not is_tool_error(status)
    assert extract_result(status)["index_status"] == "ready"
    assert extract_result(status)["indexed_file_count"] == 2
    assert extract_result(status)["chunking_summary"]["indexed_chunk_count"] >= 2

    second = call_tool(server, "req-r3", "repo.refresh_index", {"force": False})
    assert not is_tool_error(second)
    assert extract_result(second)["added"] == 0
    assert extract_result(second)["updated"] == 0
    assert extract_result(second)["removed"] == 0

    (tmp_path / "src" / "a.py").write_text("print('a changed')\n", encoding="utf-8")
    third = call_tool(server, "req-r4", "repo.refresh_index", {"force": False})
    assert not is_tool_error(third)
    assert extract_result(third)["added"] == 0
    assert extract_result(third)["updated"] == 1
    assert extract_result(third)["removed"] == 0
