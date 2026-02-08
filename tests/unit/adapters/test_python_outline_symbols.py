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
    assert symbols[0].start_line < symbols[1].start_line < symbols[2].start_line
    assert symbols[0].end_line >= symbols[1].end_line


def test_python_outline_handles_syntax_errors_deterministically() -> None:
    adapter = PythonAstAdapter()
    symbols = adapter.outline("broken.py", "def broken(:\n pass\n")
    assert symbols == []
