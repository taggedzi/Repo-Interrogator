from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_repo_status_includes_effective_config_snapshot(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_file_bytes = 2048",
                "max_open_lines = 33",
                "max_total_bytes_per_response = 4096",
                "max_search_hits = 12",
                "",
                "[index]",
                'include_extensions = [".py", ".md"]',
                'exclude_globs = ["**/.git/**", "**/.venv/**"]',
                "",
                "[adapters]",
                "python_enabled = false",
            ]
        ),
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    response = server.handle_payload({"id": "req-status-1", "method": "repo.status", "params": {}})

    assert response["ok"] is True
    result = response["result"]
    assert result["enabled_adapters"] == []
    assert result["limits_summary"] == {
        "max_file_bytes": 2048,
        "max_open_lines": 33,
        "max_total_bytes_per_response": 4096,
        "max_search_hits": 12,
        "max_references": 50,
    }

    effective = result["effective_config"]
    assert effective["repo_root"] == str(tmp_path.resolve())
    assert effective["data_dir"] == str((tmp_path / ".repo_mcp").resolve())
    assert effective["limits"] == result["limits_summary"]
    assert effective["index"]["include_extensions"] == [".py", ".md"]
    assert effective["adapters"]["python_enabled"] is False
