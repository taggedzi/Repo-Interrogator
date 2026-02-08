from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.security import PathBlockedError, resolve_repo_path


def test_symlink_escape_is_blocked(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-target"
    outside.mkdir(exist_ok=True)
    (outside / "leak.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathBlockedError) as error:
        resolve_repo_path(repo_root=tmp_path, candidate="link/leak.txt")

    assert error.value.reason == "Resolved path escapes repo_root."
