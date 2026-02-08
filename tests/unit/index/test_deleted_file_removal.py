from __future__ import annotations

from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index import detect_index_delta, discover_files, record_map


def test_deleted_file_is_reported_as_removed(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    keep = tmp_path / "src" / "keep.py"
    drop = tmp_path / "src" / "drop.py"
    keep.write_text("print('keep')\n", encoding="utf-8")
    drop.write_text("print('drop')\n", encoding="utf-8")

    config = IndexConfig(include_extensions=(".py",), exclude_globs=())
    before = discover_files(tmp_path, config=config)
    previous = record_map(before)

    drop.unlink()
    after = discover_files(tmp_path, config=config)
    delta = detect_index_delta(previous=previous, current_records=after)

    assert delta.added == ()
    assert delta.updated == ()
    assert delta.unchanged == ("src/keep.py",)
    assert delta.removed == ("src/drop.py",)
