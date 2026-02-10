from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_refresh_index_emits_refresh_profile_with_discovery_stats(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")

    server = create_server(repo_root=str(tmp_path))
    first = server.handle_payload(
        {"id": "req-prof-1", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert first["ok"] is True
    first_result = first["result"]
    assert isinstance(first_result.get("refresh_profile"), dict)
    first_profile = first_result["refresh_profile"]
    assert isinstance(first_profile.get("discovery"), dict)

    second = server.handle_payload(
        {"id": "req-prof-2", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert second["ok"] is True
    second_profile = second["result"]["refresh_profile"]
    discovery = second_profile["discovery"]
    assert discovery["unchanged_reused"] >= 1
    assert discovery["hashed_files"] == 0
