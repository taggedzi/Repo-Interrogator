from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import TypeScriptJavaScriptLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/ts_js") / name
    return path.read_text(encoding="utf-8")


def test_typescript_outline_extracts_top_level_and_methods() -> None:
    adapter = TypeScriptJavaScriptLexicalAdapter()
    source = _fixture_text("sample.ts")

    symbols = adapter.outline("src/sample.ts", source)

    assert adapter.supports_path("src/sample.ts")
    assert adapter.supports_path("src/sample.tsx")
    assert not adapter.supports_path("src/sample.py")

    names = [symbol.name for symbol in symbols]
    kinds = [symbol.kind for symbol in symbols]

    assert "Runner" in names
    assert "Mode" in names
    assert "Result" in names
    assert "Service" in names
    assert "Service.constructor" in names
    assert "Service.run" in names
    assert "Service.format" in names
    assert "build" in names
    assert "DEFAULT_NAME" in names

    by_name = {symbol.name: symbol for symbol in symbols}
    assert by_name["Runner"].kind == "interface"
    assert by_name["Mode"].kind == "enum"
    assert by_name["Result"].kind == "type_alias"
    assert by_name["build"].kind == "async_function"
    assert by_name["DEFAULT_NAME"].kind == "exported_variable"
    assert by_name["Service.run"].kind == "async_method"
    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)

    assert names == [symbol.name for symbol in adapter.outline("src/sample.ts", source)]
    assert kinds == [symbol.kind for symbol in adapter.outline("src/sample.ts", source)]
