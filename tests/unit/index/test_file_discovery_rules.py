from __future__ import annotations

from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index import discover_files


def test_discovery_honors_extensions_excludes_and_stable_order(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "src" / "z.py").write_text("print('z')\n", encoding="utf-8")
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "src" / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / ".git" / "config").write_text("internal", encoding="utf-8")

    config = IndexConfig(
        include_extensions=(".py", ".md"),
        exclude_globs=("**/.git/**",),
    )
    records = discover_files(tmp_path, config=config)

    assert [record.path for record in records] == [
        "docs/guide.md",
        "src/a.py",
        "src/z.py",
    ]


def test_discovery_excludes_binary_file_with_allowed_extension(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src" / "bad.py").write_bytes(b"\x00\x01\x02")

    config = IndexConfig(
        include_extensions=(".py",),
        exclude_globs=(),
    )
    records = discover_files(tmp_path, config=config)
    assert [record.path for record in records] == ["src/ok.py"]
