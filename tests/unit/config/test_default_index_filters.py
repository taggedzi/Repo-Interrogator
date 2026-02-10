from __future__ import annotations

from pathlib import Path

from repo_mcp.config import default_config


def test_default_config_excludes_common_cache_and_tooling_directories(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    excludes = set(config.index.exclude_globs)

    expected = {
        "**/.git/**",
        "**/.github/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/.repo_mcp/**",
        "**/.mypy_cache/**",
        "**/.pytest_cache/**",
        "**/.ruff_cache/**",
        "**/node_modules/**",
        "**/target/**",
    }
    assert expected.issubset(excludes)


def test_default_config_includes_v25_multilanguage_source_extensions(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    includes = set(config.index.include_extensions)

    expected = {
        ".py",
        ".ts",
        ".js",
        ".java",
        ".go",
        ".rs",
        ".cpp",
        ".cs",
        ".md",
        ".toml",
    }
    assert expected.issubset(includes)
