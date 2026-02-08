from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.server import create_server


def test_invalid_limit_type_raises_value_error(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[limits]",
                'max_open_lines = "not-an-int"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="limits.max_open_lines"):
        create_server(repo_root=str(tmp_path))


def test_invalid_section_type_raises_value_error(tmp_path: Path) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                'limits = "not-a-table"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="section 'limits'"):
        create_server(repo_root=str(tmp_path))
