from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import CppLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/cpp") / name
    return path.read_text(encoding="utf-8")


def test_cpp_outline_extracts_namespace_types_methods_and_functions() -> None:
    adapter = CppLexicalAdapter()
    source = _fixture_text("sample.cpp")

    symbols = adapter.outline("src/sample.cpp", source)

    assert adapter.supports_path("src/main.cpp")
    assert adapter.supports_path("include/main.hpp")
    assert adapter.supports_path("include/main.h")
    assert not adapter.supports_path("src/main.rs")

    names = [symbol.name for symbol in symbols]
    by_kind_name = {(symbol.kind, symbol.name): symbol for symbol in symbols}

    assert "engine" in names
    assert "Service" in names
    assert "Config" in names
    assert "Mode" in names
    assert "Service.Service" in names
    assert "Service.run" in names
    assert "Service.make" in names
    assert "Config.enabled" in names
    assert "parse_value" in names

    assert ("namespace", "engine") in by_kind_name
    assert ("class", "Service") in by_kind_name
    assert ("struct", "Config") in by_kind_name
    assert ("enum", "Mode") in by_kind_name
    assert ("method", "Service.Service") in by_kind_name
    assert ("method", "Service.run") in by_kind_name
    assert ("method", "Service.make") in by_kind_name
    assert ("method", "Config.enabled") in by_kind_name
    assert ("function", "parse_value") in by_kind_name

    assert by_kind_name[("method", "Service.run")].signature == "(int value)"
    assert by_kind_name[("function", "parse_value")].signature == "(int input)"
    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)


def test_cpp_outline_is_deterministic_for_repeated_calls() -> None:
    adapter = CppLexicalAdapter()
    source = _fixture_text("sample.cpp")

    first = adapter.outline("src/sample.cpp", source)
    second = adapter.outline("src/sample.cpp", source)

    assert [(s.kind, s.name, s.start_line, s.end_line) for s in first] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in second
    ]
