from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import CSharpLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/csharp") / name
    return path.read_text(encoding="utf-8")


def test_csharp_outline_extracts_namespace_types_and_members() -> None:
    adapter = CSharpLexicalAdapter()
    source = _fixture_text("sample.cs")

    symbols = adapter.outline("src/sample.cs", source)

    assert adapter.supports_path("src/Program.cs")
    assert not adapter.supports_path("src/program.go")

    names = [symbol.name for symbol in symbols]
    by_kind_name = {(symbol.kind, symbol.name): symbol for symbol in symbols}

    assert "Acme.Tools" in names
    assert "Acme.Tools.IRunner" in names
    assert "Acme.Tools.Mode" in names
    assert "Acme.Tools.Result" in names
    assert "Acme.Tools.Service" in names
    assert "Acme.Tools.Service.Name" in names
    assert "Acme.Tools.Service.Changed" in names
    assert "Acme.Tools.Service.Service" in names
    assert "Acme.Tools.Service.RunAsync" in names
    assert "Acme.Tools.Service.Build" in names

    assert ("namespace", "Acme.Tools") in by_kind_name
    assert ("interface", "Acme.Tools.IRunner") in by_kind_name
    assert ("enum", "Acme.Tools.Mode") in by_kind_name
    assert ("record", "Acme.Tools.Result") in by_kind_name
    assert ("class", "Acme.Tools.Service") in by_kind_name
    assert ("property", "Acme.Tools.Service.Name") in by_kind_name
    assert ("event", "Acme.Tools.Service.Changed") in by_kind_name
    assert ("constructor", "Acme.Tools.Service.Service") in by_kind_name
    assert ("method", "Acme.Tools.Service.RunAsync") in by_kind_name
    assert ("method", "Acme.Tools.Service.Build") in by_kind_name

    assert by_kind_name[("method", "Acme.Tools.Service.Build")].signature == "(string name)"
    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)


def test_csharp_outline_is_deterministic_on_repeated_calls() -> None:
    adapter = CSharpLexicalAdapter()
    source = _fixture_text("sample.cs")

    first = adapter.outline("src/sample.cs", source)
    second = adapter.outline("src/sample.cs", source)

    assert [(s.kind, s.name, s.start_line, s.end_line) for s in first] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in second
    ]
