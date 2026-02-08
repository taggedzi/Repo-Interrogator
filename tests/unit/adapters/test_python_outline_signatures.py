from __future__ import annotations

from repo_mcp.adapters import PythonAstAdapter


def test_python_outline_captures_signatures() -> None:
    source = """
class Service(BaseA, BaseB):
    async def run(self, item: str, retries: int = 2) -> str:
        return item

def build(name: str, *, force: bool = False) -> str:
    return name
"""
    adapter = PythonAstAdapter()
    symbols = adapter.outline("svc.py", source)

    by_name = {symbol.name: symbol for symbol in symbols}
    assert by_name["Service"].signature == "(BaseA, BaseB)"
    assert by_name["Service.run"].signature == "(self, item: str, retries: int=2)"
    assert by_name["build"].signature == "(name: str, *, force: bool=False)"
    assert by_name["Service.run"].kind == "async_method"
