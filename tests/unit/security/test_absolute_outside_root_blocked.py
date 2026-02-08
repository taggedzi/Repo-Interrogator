from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.security import PathBlockedError, resolve_repo_path


def test_absolute_path_outside_root_is_blocked(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("x", encoding="utf-8")

    with pytest.raises(PathBlockedError) as error:
        resolve_repo_path(repo_root=tmp_path, candidate=str(outside_file))

    assert error.value.reason == "Absolute path is outside repo_root."
