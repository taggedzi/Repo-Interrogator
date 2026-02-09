from __future__ import annotations

from repo_mcp.adapters import PythonAstAdapter


def test_python_outline_extracts_classes_methods_functions() -> None:
    source = """
class Worker:
    \"\"\"Worker class doc.\"\"\"

    def run(self, value: int) -> int:
        \"\"\"Run work.\"\"\"
        return value + 1

def helper(flag: bool) -> bool:
    \"\"\"Helper function.\"\"\"
    return flag
"""
    adapter = PythonAstAdapter()
    symbols = adapter.outline("pkg/worker.py", source)

    assert [symbol.kind for symbol in symbols] == ["class", "method", "function"]
    assert [symbol.name for symbol in symbols] == ["Worker", "Worker.run", "helper"]
    assert symbols[0].doc == "Worker class doc."
    assert symbols[1].doc == "Run work."
    assert symbols[2].doc == "Helper function."
    assert symbols[0].parent_symbol is None
    assert symbols[0].scope_kind == "module"
    assert symbols[0].is_conditional is False
    assert symbols[0].decl_context is None
    assert symbols[1].parent_symbol == "Worker"
    assert symbols[1].scope_kind == "class"
    assert symbols[1].is_conditional is False
    assert symbols[2].parent_symbol is None
    assert symbols[2].scope_kind == "module"
    assert symbols[0].start_line < symbols[1].start_line < symbols[2].start_line
    assert symbols[0].end_line >= symbols[1].end_line


def test_python_outline_handles_syntax_errors_deterministically() -> None:
    adapter = PythonAstAdapter()
    symbols = adapter.outline("broken.py", "def broken(:\n pass\n")
    assert symbols == []


def test_python_outline_includes_nested_and_conditional_declarations() -> None:
    source = """
if True:
    def under_if() -> None:
        pass

class Outer:
    def method(self) -> None:
        def local_fn() -> None:
            pass

        class Local:
            def run(self) -> None:
                pass

def top() -> None:
    if False:
        def under_nested_if() -> None:
            pass
"""
    adapter = PythonAstAdapter()
    symbols = adapter.outline("nested.py", source)

    expected_names = [
        "under_if",
        "Outer",
        "Outer.method",
        "Outer.method.local_fn",
        "Outer.method.Local",
        "Outer.method.Local.run",
        "top",
        "top.under_nested_if",
    ]
    assert [symbol.name for symbol in symbols] == expected_names

    by_name = {symbol.name: symbol for symbol in symbols}
    assert by_name["Outer.method"].kind == "method"
    assert by_name["Outer.method.local_fn"].kind == "function"
    assert by_name["Outer.method.Local"].kind == "class"
    assert by_name["Outer.method.Local.run"].kind == "method"
    assert by_name["top.under_nested_if"].kind == "function"
    assert by_name["under_if"].is_conditional is True
    assert by_name["under_if"].decl_context == "if"
    assert by_name["Outer"].is_conditional is False
    assert by_name["Outer.method.local_fn"].parent_symbol == "Outer.method"
    assert by_name["Outer.method.local_fn"].scope_kind == "function"
    assert by_name["top.under_nested_if"].is_conditional is True
    assert by_name["top.under_nested_if"].decl_context == "if"


def test_python_outline_handles_ast_value_error_deterministically() -> None:
    adapter = PythonAstAdapter()
    symbols = adapter.outline("nul.py", "def ok():\n    pass\0\n")
    assert symbols == []
