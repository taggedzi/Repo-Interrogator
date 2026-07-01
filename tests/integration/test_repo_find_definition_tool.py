from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_repo_find_definition_returns_declaration_site(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from service import Service\n\nsvc = Service()\nsvc.run()\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(
        server, "req-def-1", "repo.find_definition", {"symbol": "Service.run", "top_k": 10}
    )
    assert not is_tool_error(response)
    result = extract_result(response)

    assert result["symbol"] == "Service.run"
    assert result["definitions"] == [
        {
            "path": "src/service.py",
            "start_line": 2,
            "end_line": 3,
            "kind": "method",
            "signature": "(self)",
            "scope_kind": "class",
        }
    ]
    assert result["truncated"] is False
    assert result["total_candidates"] == 1


def test_repo_find_definition_unknown_symbol_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(
        server, "req-def-2", "repo.find_definition", {"symbol": "NoSuchSymbol", "top_k": 10}
    )
    assert not is_tool_error(response)
    result = extract_result(response)

    assert result["definitions"] == []
    assert result["total_candidates"] == 0
    assert result["truncated"] is False


def test_repo_find_definition_path_scope_and_truncation(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    scoped = extract_result(
        call_tool(
            server,
            "req-def-scope-1",
            "repo.find_definition",
            {"symbol": "handler", "path": "src/a.py", "top_k": 10},
        )
    )
    assert [item["path"] for item in scoped["definitions"]] == ["src/a.py"]

    truncated = extract_result(
        call_tool(
            server, "req-def-scope-2", "repo.find_definition", {"symbol": "handler", "top_k": 1}
        )
    )
    assert truncated["truncated"] is True
    assert truncated["total_candidates"] == 2
    assert len(truncated["definitions"]) == 1


def test_repo_find_definition_requires_non_empty_symbol(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(server, "req-def-3", "repo.find_definition", {"symbol": "  "})
    assert is_tool_error(response)
