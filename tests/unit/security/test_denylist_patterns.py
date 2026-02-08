from __future__ import annotations

from pathlib import Path

from repo_mcp.security import is_denylisted


def test_denylist_blocks_sensitive_patterns(tmp_path: Path) -> None:
    candidates = [
        tmp_path / ".env",
        tmp_path / "tls.pem",
        tmp_path / "private.key",
        tmp_path / "bundle.pfx",
        tmp_path / "archive.p12",
        tmp_path / "id_rsa",
        tmp_path / "id_rsa.pub",
        tmp_path / "config" / "secrets.toml",
        tmp_path / ".git" / "config",
    ]
    for path in candidates:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    for path in candidates:
        assert is_denylisted(repo_root=tmp_path, resolved_path=path.resolve()), path.as_posix()


def test_denylist_allows_regular_file(tmp_path: Path) -> None:
    path = tmp_path / "src" / "main.py"
    path.parent.mkdir(parents=True)
    path.write_text("print('ok')\n", encoding="utf-8")

    assert not is_denylisted(repo_root=tmp_path, resolved_path=path.resolve())
