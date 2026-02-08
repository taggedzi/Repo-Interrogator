from __future__ import annotations

from pathlib import Path

from repo_mcp.config import CliOverrides
from repo_mcp.server import create_server


def test_merge_order_defaults_then_repo_then_cli(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_open_lines = 42",
                "max_search_hits = 7",
                "",
                "[adapters]",
                "python_enabled = false",
            ]
        ),
        encoding="utf-8",
    )
    overrides = CliOverrides(max_open_lines=99, python_enabled=True)
    server = create_server(repo_root=str(tmp_path), cli_overrides=overrides)

    response = server.handle_payload({"id": "req-merge", "method": "repo.status", "params": {}})
    effective = response["result"]["effective_config"]

    assert effective["limits"]["max_open_lines"] == 99
    assert effective["limits"]["max_search_hits"] == 7
    assert effective["adapters"]["python_enabled"] is True


def test_data_dir_override_has_highest_precedence(tmp_path: Path) -> None:
    custom_data_dir = tmp_path / ".custom_data"
    server = create_server(
        repo_root=str(tmp_path),
        cli_overrides=CliOverrides(data_dir=custom_data_dir),
    )

    response = server.handle_payload({"id": "req-data-dir", "method": "repo.status", "params": {}})
    effective = response["result"]["effective_config"]
    assert effective["data_dir"] == str(custom_data_dir.resolve())
