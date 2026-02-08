from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.config import load_effective_config


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("denylist_override", "true"),
        ("denylist_allowlist", "['.env']"),
        ("denylist_relax", "true"),
    ],
)
def test_denylist_relaxation_keys_are_rejected(tmp_path: Path, key: str, value: str) -> None:
    (tmp_path / "repo_mcp.toml").write_text(
        "\n".join(
            [
                "[security]",
                f"{key} = {value}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="denylist"):
        load_effective_config(repo_root=tmp_path)
