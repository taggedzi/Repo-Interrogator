from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import build_adapter_registry
from repo_mcp.config import CliOverrides, load_effective_config


def test_registry_selects_expected_adapter_for_known_extensions(tmp_path: Path) -> None:
    config = load_effective_config(tmp_path)
    registry = build_adapter_registry(config)

    assert registry.select("src/mod.py").name == "python"
    assert registry.select("src/mod.ts").name == "ts_js_lexical"
    assert registry.select("src/mod.js").name == "ts_js_lexical"
    assert registry.select("src/Mod.java").name == "java_lexical"
    assert registry.select("src/mod.go").name == "go_lexical"
    assert registry.select("src/mod.rs").name == "rust_lexical"
    assert registry.select("src/mod.cpp").name == "cpp_lexical"
    assert registry.select("src/Mod.cs").name == "csharp_lexical"
    assert registry.select("docs/notes.md").name == "lexical"


def test_registry_falls_back_to_lexical_for_python_when_python_disabled(tmp_path: Path) -> None:
    config = load_effective_config(tmp_path, overrides=CliOverrides(python_enabled=False))
    registry = build_adapter_registry(config)

    assert registry.select("src/mod.py").name == "lexical"
