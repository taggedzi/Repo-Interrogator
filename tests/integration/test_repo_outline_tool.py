from __future__ import annotations

from pathlib import Path

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

    response = server.handle_payload(
        {"id": "req-outline-1", "method": "repo.outline", "params": {"path": "src/mod.py"}}
    )
    assert response["ok"] is True
    result = response["result"]
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


def test_repo_outline_tool_uses_lexical_fallback_for_non_python(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    md_file = tmp_path / "docs" / "notes.md"
    md_file.write_text("# Notes\n- item\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    response = server.handle_payload(
        {"id": "req-outline-2", "method": "repo.outline", "params": {"path": "docs/notes.md"}}
    )
    assert response["ok"] is True
    assert response["result"]["language"] == "lexical"
    assert response["result"]["symbols"] == []
