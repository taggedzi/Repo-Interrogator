from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_refresh_index_roundtrip_and_status_snapshot(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    first = server.handle_payload(
        {"id": "req-r1", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert first["ok"] is True
    assert first["result"]["added"] == 2
    assert first["result"]["updated"] == 0
    assert first["result"]["removed"] == 0
    assert isinstance(first["result"]["timestamp"], str)

    status = server.handle_payload({"id": "req-r2", "method": "repo.status", "params": {}})
    assert status["ok"] is True
    assert status["result"]["index_status"] == "ready"
    assert status["result"]["indexed_file_count"] == 2
    assert status["result"]["chunking_summary"]["indexed_chunk_count"] >= 2

    second = server.handle_payload(
        {"id": "req-r3", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert second["ok"] is True
    assert second["result"]["added"] == 0
    assert second["result"]["updated"] == 0
    assert second["result"]["removed"] == 0

    (tmp_path / "src" / "a.py").write_text("print('a changed')\n", encoding="utf-8")
    third = server.handle_payload(
        {"id": "req-r4", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert third["ok"] is True
    assert third["result"]["added"] == 0
    assert third["result"]["updated"] == 1
    assert third["result"]["removed"] == 0
