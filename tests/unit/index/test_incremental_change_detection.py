from __future__ import annotations

from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index import detect_index_delta, discover_files, record_map


def test_incremental_change_detection_added_updated_unchanged(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    alpha = tmp_path / "src" / "alpha.py"
    beta = tmp_path / "src" / "beta.py"
    alpha.write_text("print('alpha v1')\n", encoding="utf-8")
    beta.write_text("print('beta v1')\n", encoding="utf-8")

    config = IndexConfig(include_extensions=(".py",), exclude_globs=())
    before = discover_files(tmp_path, config=config)
    previous = record_map(before)

    alpha.write_text("print('alpha v2 changed')\n", encoding="utf-8")
    gamma = tmp_path / "src" / "gamma.py"
    gamma.write_text("print('gamma')\n", encoding="utf-8")

    after = discover_files(tmp_path, config=config)
    delta = detect_index_delta(previous=previous, current_records=after)

    assert delta.added == ("src/gamma.py",)
    assert delta.updated == ("src/alpha.py",)
    assert delta.unchanged == ("src/beta.py",)
    assert delta.removed == ()
