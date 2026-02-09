from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import RustLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/rust") / name
    return path.read_text(encoding="utf-8")


def test_rust_outline_extracts_top_level_and_impl_symbols() -> None:
    adapter = RustLexicalAdapter()
    source = _fixture_text("sample.rs")

    symbols = adapter.outline("src/sample.rs", source)

    assert adapter.supports_path("src/lib.rs")
    assert not adapter.supports_path("src/lib.go")

    names = [symbol.name for symbol in symbols]
    by_kind_name = {(symbol.kind, symbol.name): symbol for symbol in symbols}

    assert "engine" in names
    assert "Service" in names
    assert "Mode" in names
    assert "Runner" in names
    assert "DEFAULT_NAME" in names
    assert "ResultText" in names
    assert "build" in names
    assert "Service" in [s.name for s in symbols if s.kind == "impl"]
    assert "Service.new" in names
    assert "Service.run" in names

    assert ("mod", "engine") in by_kind_name
    assert ("struct", "Service") in by_kind_name
    assert ("impl", "Service") in by_kind_name
    assert ("enum", "Mode") in by_kind_name
    assert ("trait", "Runner") in by_kind_name
    assert ("const", "DEFAULT_NAME") in by_kind_name
    assert ("type", "ResultText") in by_kind_name
    assert ("function", "build") in by_kind_name
    assert ("method", "Service.new") in by_kind_name
    assert ("method", "Service.run") in by_kind_name
    assert by_kind_name[("method", "Service.new")].signature == "(name: String)"

    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)


def test_rust_outline_is_deterministic_for_repeated_calls() -> None:
    adapter = RustLexicalAdapter()
    source = _fixture_text("sample.rs")

    first = adapter.outline("src/sample.rs", source)
    second = adapter.outline("src/sample.rs", source)

    assert [(s.kind, s.name, s.start_line, s.end_line) for s in first] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in second
    ]
