from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import JavaLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/java") / name
    return path.read_text(encoding="utf-8")


def test_java_outline_extracts_package_types_and_members() -> None:
    adapter = JavaLexicalAdapter()
    source = _fixture_text("sample.java")

    symbols = adapter.outline("src/sample.java", source)

    assert adapter.supports_path("src/Main.java")
    assert not adapter.supports_path("src/Main.kt")

    names = [symbol.name for symbol in symbols]
    by_name = {symbol.name: symbol for symbol in symbols}

    assert "com.example.service.Runner" in names
    assert "com.example.service.Mode" in names
    assert "com.example.service.Result" in names
    assert "com.example.service.Service" in names
    assert "com.example.service.Service.Service" in names
    assert "com.example.service.Service.run" in names
    assert "com.example.service.Service.parse" in names

    assert by_name["com.example.service.Runner"].kind == "interface"
    assert by_name["com.example.service.Mode"].kind == "enum"
    assert by_name["com.example.service.Result"].kind == "type"
    assert by_name["com.example.service.Service"].kind == "class"
    assert by_name["com.example.service.Service.Service"].kind == "constructor"
    assert by_name["com.example.service.Service.run"].kind == "method"
    assert by_name["com.example.service.Service.parse"].kind == "method"
    assert by_name["com.example.service.Service.parse"].signature == "(int value)"

    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)


def test_java_outline_is_deterministic_for_repeated_calls() -> None:
    adapter = JavaLexicalAdapter()
    source = _fixture_text("sample.java")

    first = adapter.outline("src/sample.java", source)
    second = adapter.outline("src/sample.java", source)

    assert [(s.kind, s.name, s.start_line, s.end_line) for s in first] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in second
    ]
