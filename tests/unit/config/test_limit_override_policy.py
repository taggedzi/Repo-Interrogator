from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.config import CliOverrides, load_effective_config


def test_repo_config_limit_above_cap_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_search_hits = 500",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="max_search_hits"):
        load_effective_config(repo_root=tmp_path)


def test_cli_override_limit_above_cap_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="overrides.max_open_lines"):
        load_effective_config(
            repo_root=tmp_path,
            overrides=CliOverrides(max_open_lines=5000),
        )


def test_repo_and_cli_overrides_within_caps_are_applied(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                "max_file_bytes = 2000000",
                "max_open_lines = 800",
                "max_total_bytes_per_response = 500000",
                "max_search_hits = 120",
            ]
        ),
        encoding="utf-8",
    )
    config = load_effective_config(
        repo_root=tmp_path,
        overrides=CliOverrides(max_search_hits=150),
    )

    assert config.limits.max_file_bytes == 2000000
    assert config.limits.max_open_lines == 800
    assert config.limits.max_total_bytes_per_response == 500000
    assert config.limits.max_search_hits == 150
