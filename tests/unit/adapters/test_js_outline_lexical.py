from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import TypeScriptJavaScriptLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/ts_js") / name
    return path.read_text(encoding="utf-8")


def test_javascript_outline_extracts_functions_methods_and_exports() -> None:
    adapter = TypeScriptJavaScriptLexicalAdapter()
    source = _fixture_text("sample.js")

    symbols = adapter.outline("src/sample.js", source)

    assert adapter.supports_path("src/sample.js")
    assert adapter.supports_path("src/sample.mjs")
    assert adapter.supports_path("src/sample.cjs")

    names = [symbol.name for symbol in symbols]

    assert "Worker" in names
    assert "Worker.run" in names
    assert "Worker.from" in names
    assert "helper" in names
    assert "helper" in [s.name for s in symbols if s.kind == "exported_variable"]
    assert "main" in [s.name for s in symbols if s.kind == "exported_variable"]
    assert "VERSION" in [s.name for s in symbols if s.kind == "exported_variable"]

    by_name = {symbol.name: symbol for symbol in symbols if symbol.kind != "exported_variable"}
    assert by_name["Worker"].kind == "class"
    assert by_name["helper"].kind == "function"
    assert by_name["Worker.run"].kind == "method"
    assert by_name["Worker.from"].kind == "method"
    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)

    repeat = adapter.outline("src/sample.js", source)
    assert [(s.kind, s.name, s.start_line, s.end_line) for s in symbols] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in repeat
    ]
