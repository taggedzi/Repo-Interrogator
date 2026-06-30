from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_repo_outline_tool_uses_python_adapter(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    py_file = tmp_path / "src" / "mod.py"
    py_file.write_text(
        "class A:\n"
        "    def m(self, x: int) -> int:\n"
        "        return x\n"
        "\n"
        "def f(y: str) -> str:\n"
        "    return y\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(
        call_tool(server, "req-outline-1", "repo.outline", {"path": "src/mod.py"})
    )

    assert result["language"] == "python"
    assert result["path"] == "src/mod.py"
    names = [symbol["name"] for symbol in result["symbols"]]
    assert names == ["A", "A.m", "f"]
    assert set(result["symbols"][0].keys()) == {
        "kind",
        "name",
        "signature",
        "start_line",
        "end_line",
        "doc",
        "parent_symbol",
        "scope_kind",
        "is_conditional",
        "decl_context",
    }
    assert result["symbols"][0]["scope_kind"] == "module"
    assert result["symbols"][0]["parent_symbol"] is None
    assert result["symbols"][0]["is_conditional"] is False
    assert result["symbols"][1]["scope_kind"] == "class"
    assert result["symbols"][1]["parent_symbol"] == "A"
    assert result["symbols"][2]["scope_kind"] == "module"
