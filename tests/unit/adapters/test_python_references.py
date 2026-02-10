from __future__ import annotations

import ast

from repo_mcp.adapters import PythonAstAdapter


def test_python_references_for_symbol_links_cross_file_usages() -> None:
    files = [
        (
            "src/service.py",
            """
class Service:
    def run(self) -> int:
        return 1
""",
        ),
        (
            "src/app.py",
            """
from service import Service


def use_service() -> int:
    svc = Service()
    return svc.run()
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("Service.run", files)

    assert [item.path for item in references] == ["src/app.py"]
    assert [item.kind for item in references] == ["call"]
    assert [item.line for item in references] == [7]
    assert references[0].symbol == "Service.run"
    assert references[0].strategy == "ast"


def test_python_references_for_symbol_are_deterministic_and_sorted() -> None:
    files = [
        (
            "src/b.py",
            """
from service import Service

def f() -> None:
    Service().run()
""",
        ),
        (
            "src/a.py",
            """
from service import Service

def g() -> None:
    Service().run()
""",
        ),
    ]

    adapter = PythonAstAdapter()
    first = adapter.references_for_symbol("Service.run", files)
    second = adapter.references_for_symbol("Service.run", files)

    assert first == second
    assert [(item.path, item.line, item.symbol, item.kind) for item in first] == [
        ("src/a.py", 5, "Service.run", "call"),
        ("src/b.py", 5, "Service.run", "call"),
    ]


def test_python_references_for_symbol_top_k_is_applied_after_sorting() -> None:
    files = [
        (
            "src/a.py",
            """
def a() -> None:
    Service().run()
""",
        ),
        (
            "src/b.py",
            """
def b() -> None:
    Service().run()
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("Service.run", files, top_k=1)

    assert len(references) == 1
    assert references[0].path == "src/a.py"


def test_python_references_for_symbol_skips_non_python_and_parse_failures() -> None:
    files = [
        ("src/a.py", "def f(:\n    pass\n"),
        ("docs/readme.md", "Service.run"),
        (
            "src/b.py",
            """
def call() -> None:
    Service().run()
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("Service.run", files)

    assert len(references) == 1
    assert references[0].path == "src/b.py"


def test_python_references_reuses_cached_candidates_between_symbols(monkeypatch) -> None:
    files = [
        (
            "src/a.py",
            """
class Service:
    def run(self) -> int:
        return 1

def call() -> int:
    return Service().run()
""",
        )
    ]
    parse_calls = 0
    original_parse = ast.parse

    def wrapped_parse(*args, **kwargs):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(ast, "parse", wrapped_parse)
    adapter = PythonAstAdapter()
    first = adapter.references_for_symbol("Service", files)
    second = adapter.references_for_symbol("Service.run", files)

    assert first
    assert second
    assert parse_calls == 1
