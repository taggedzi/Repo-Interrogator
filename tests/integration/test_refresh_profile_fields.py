from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_refresh_index_emits_refresh_profile_with_discovery_stats(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")

    server = create_server(repo_root=str(tmp_path))
    first = call_tool(server, "req-prof-1", "repo.refresh_index", {"force": False})
    assert not is_tool_error(first)
    first_result = extract_result(first)
    assert isinstance(first_result.get("refresh_profile"), dict)
    first_profile = first_result["refresh_profile"]
    assert isinstance(first_profile.get("discovery"), dict)

    second = call_tool(server, "req-prof-2", "repo.refresh_index", {"force": False})
    assert not is_tool_error(second)
    second_profile = extract_result(second)["refresh_profile"]
    discovery = second_profile["discovery"]
    assert discovery["unchanged_reused"] >= 1
    assert discovery["hashed_files"] == 0
