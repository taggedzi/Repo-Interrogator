from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from repo_mcp.config import IndexConfig
from repo_mcp.index.discovery import discover_files


def test_discover_files_reuses_hash_when_size_and_mtime_match(tmp_path: Path) -> None:
    target = tmp_path / "src" / "alpha.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('alpha')\n", encoding="utf-8")

    config = IndexConfig(include_extensions=(".py",), exclude_globs=())
    first = discover_files(tmp_path, config=config)
    assert len(first) == 1
    previous = {first[0].path: first[0]}

    with patch("repo_mcp.index.discovery.sha256_file") as sha_mock:
        second = discover_files(tmp_path, config=config, previous_records=previous)

    assert len(second) == 1
    assert second[0] == first[0]
    sha_mock.assert_not_called()


def test_discover_files_profiles_reused_and_hashed_counts(tmp_path: Path) -> None:
    first_path = tmp_path / "src" / "alpha.py"
    second_path = tmp_path / "src" / "beta.py"
    first_path.parent.mkdir(parents=True)
    first_path.write_text("print('alpha')\n", encoding="utf-8")
    second_path.write_text("print('beta v1')\n", encoding="utf-8")

    config = IndexConfig(include_extensions=(".py",), exclude_globs=())
    initial = discover_files(tmp_path, config=config)
    previous = {item.path: item for item in initial}

    second_path.write_text("print('beta v2 changed')\n", encoding="utf-8")
    profile: dict[str, object] = {}
    updated = discover_files(
        tmp_path,
        config=config,
        previous_records=previous,
        profile=profile,
    )

    assert len(updated) == 2
    assert isinstance(profile.get("unchanged_reused"), int)
    assert isinstance(profile.get("hashed_files"), int)
    assert profile["unchanged_reused"] == 1
    assert profile["hashed_files"] == 1
    assert profile["binary_excluded"] == 0
    assert profile["total_candidates"] == 2
