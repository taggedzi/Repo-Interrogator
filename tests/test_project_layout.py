from __future__ import annotations

from pathlib import Path


def test_required_package_paths_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        "src/repo_mcp/server.py",
        "src/repo_mcp/tools/__init__.py",
        "src/repo_mcp/index/__init__.py",
        "src/repo_mcp/adapters/__init__.py",
        "src/repo_mcp/bundler/__init__.py",
        "src/repo_mcp/security/__init__.py",
        "src/repo_mcp/logging/__init__.py",
    ]
    for rel in required:
        assert (root / rel).exists(), rel
