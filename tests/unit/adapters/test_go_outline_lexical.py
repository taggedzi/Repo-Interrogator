from __future__ import annotations

from pathlib import Path

from repo_mcp.adapters import GoLexicalAdapter


def _fixture_text(name: str) -> str:
    path = Path("tests/fixtures/adapters/go") / name
    return path.read_text(encoding="utf-8")


def test_go_outline_extracts_package_types_funcs_methods_consts_vars() -> None:
    adapter = GoLexicalAdapter()
    source = _fixture_text("sample.go")

    symbols = adapter.outline("src/sample.go", source)

    assert adapter.supports_path("src/main.go")
    assert not adapter.supports_path("src/main.rs")

    names = [symbol.name for symbol in symbols]
    by_name = {symbol.name: symbol for symbol in symbols}

    assert "worker.Runner" in names
    assert "worker.Service" in names
    assert "worker.DefaultName" in names
    assert "worker.MaxRetries" in names
    assert "worker.GlobalEnabled" in names
    assert "worker.globalVersion" in names
    assert "worker.Build" in names
    assert "worker.Service.Run" in names

    assert by_name["worker.Runner"].kind == "type"
    assert by_name["worker.Service"].kind == "type"
    assert by_name["worker.DefaultName"].kind == "const"
    assert by_name["worker.GlobalEnabled"].kind == "var"
    assert by_name["worker.Build"].kind == "function"
    assert by_name["worker.Build"].signature == "(name string)"
    assert by_name["worker.Service.Run"].kind == "method"
    assert by_name["worker.Service.Run"].signature == "(ctx context.Context)"

    assert all(symbol.end_line >= symbol.start_line for symbol in symbols)


def test_go_outline_is_deterministic_on_repeated_calls() -> None:
    adapter = GoLexicalAdapter()
    source = _fixture_text("sample.go")

    first = adapter.outline("src/sample.go", source)
    second = adapter.outline("src/sample.go", source)

    assert [(s.kind, s.name, s.start_line, s.end_line) for s in first] == [
        (s.kind, s.name, s.start_line, s.end_line) for s in second
    ]
