from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.server import create_server


def test_force_refresh_rebuilds_when_schema_mismatched(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    index_dir = tmp_path / ".repo_mcp" / "index"
    index_dir.mkdir(parents=True)
    (index_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "last_refresh_timestamp": "2026-02-08T00:00:00.000Z",
                "indexed_file_count": 0,
                "indexed_chunk_count": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    response = server.handle_payload(
        {"id": "req-force", "method": "repo.refresh_index", "params": {"force": True}}
    )

    assert response["ok"] is True
    assert response["result"]["added"] == 1
    assert response["result"]["updated"] == 0
    assert response["result"]["removed"] == 0

    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["indexed_file_count"] == 1
    assert manifest["indexed_chunk_count"] >= 1
