from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import call_tool, is_tool_error, tool_error_text

from repo_mcp.server import create_server


def test_schema_version_mismatch_returns_explicit_error(tmp_path: Path) -> None:
    index_dir = tmp_path / ".repo_mcp" / "index"
    index_dir.mkdir(parents=True)
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 999,
                "last_refresh_timestamp": "2026-02-08T00:00:00.000Z",
                "indexed_file_count": 1,
                "indexed_chunk_count": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (index_dir / "files.jsonl").write_text(
        json.dumps(
            {
                "path": "src/a.py",
                "size": 1,
                "mtime_ns": 1,
                "content_hash": "deadbeef",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    response = call_tool(server, "req-schema", "repo.refresh_index", {"force": False})

    assert is_tool_error(response)
    text = tool_error_text(response)
    assert "INDEX_SCHEMA_UNSUPPORTED" in text or "schema" in text.lower()
    assert "force=true" in text
