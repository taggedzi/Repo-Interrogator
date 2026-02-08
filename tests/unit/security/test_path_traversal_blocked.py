from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.security import PathBlockedError, resolve_repo_path


def test_path_traversal_is_blocked(tmp_path: Path) -> None:
    with pytest.raises(PathBlockedError) as error:
        resolve_repo_path(repo_root=tmp_path, candidate="../outside.txt")

    assert error.value.reason == "Path traversal is blocked."
