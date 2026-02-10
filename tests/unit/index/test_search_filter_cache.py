from __future__ import annotations

from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index.manager import IndexManager


def _build_manager(tmp_path: Path) -> IndexManager:
    repo_root = tmp_path / "repo"
    data_dir = repo_root / ".repo_mcp"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (repo_root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    manager = IndexManager(
        repo_root=repo_root,
        data_dir=data_dir,
        index_config=IndexConfig(include_extensions=(".py", ".md"), exclude_globs=()),
    )
    manager.refresh(force=False)
    return manager


def test_filtered_search_docs_reused_for_same_filters(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    first = manager._load_filtered_search_documents(file_glob=None, path_prefix="src/")
    second = manager._load_filtered_search_documents(file_glob=None, path_prefix="src/")

    assert first is second
    assert first
    assert all(item.path.startswith("src/") for item in first)


def test_filtered_search_docs_cache_invalidates_after_refresh(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    repo_root = tmp_path / "repo"

    before = manager._load_filtered_search_documents(file_glob=None, path_prefix="src/")
    (repo_root / "src" / "new_file.py").write_text("VALUE = 1\n", encoding="utf-8")
    manager.refresh(force=False)
    after = manager._load_filtered_search_documents(file_glob=None, path_prefix="src/")

    assert before is not after
    assert len(after) >= len(before)
