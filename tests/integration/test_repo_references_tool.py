from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result

from repo_mcp.server import create_server


def test_repo_references_tool_returns_deterministic_structured_payload(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from service import Service\n\nsvc = Service()\nsvc.run()\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "service.ts").write_text(
        "export class Service { run(input: string): string { return input; } }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.ts").write_text(
        'import { Service } from "./service";\nconst svc = new Service();\nsvc.run("ok");\n',
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    first = extract_result(
        call_tool(server, "req-ref-1", "repo.references", {"symbol": "Service.run", "top_k": 10})
    )
    second = extract_result(
        call_tool(server, "req-ref-2", "repo.references", {"symbol": "Service.run", "top_k": 10})
    )

    assert first == second
    assert set(first.keys()) == {"symbol", "references", "truncated", "total_candidates"}
    assert first["symbol"] == "Service.run"
    assert isinstance(first["references"], list)
    assert first["total_candidates"] == len(first["references"])
    assert first["truncated"] is False

    if first["references"]:
        first_ref = first["references"][0]
        assert set(first_ref.keys()) == {
            "symbol",
            "path",
            "line",
            "kind",
            "evidence",
            "strategy",
            "confidence",
        }


def test_repo_references_tool_path_scope_and_truncation(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text(
        "const svc = new Service();\nsvc.run('a');\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "b.ts").write_text(
        "const svc = new Service();\nsvc.run('b');\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    scoped = extract_result(
        call_tool(
            server,
            "req-ref-scope-1",
            "repo.references",
            {"symbol": "Service.run", "path": "src/a.ts", "top_k": 10},
        )
    )
    assert scoped["references"]
    assert {item["path"] for item in scoped["references"]} == {"src/a.ts"}

    truncated = extract_result(
        call_tool(
            server, "req-ref-scope-2", "repo.references", {"symbol": "Service.run", "top_k": 1}
        )
    )
    assert truncated["truncated"] is True
    assert truncated["total_candidates"] >= 2
    assert len(truncated["references"]) == 1


def test_repo_references_skips_excluded_dirs_and_non_indexed_extensions(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "src" / "api.ts").write_text(
        "export class Api { run(): void {} }\nconst api = new Api();\napi.run();\n",
        encoding="utf-8",
    )
    (tmp_path / ".pytest_cache" / "noise.ts").write_text(
        "const api = new Api();\napi.run();\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text(
        "Api.run Api.run Api.run\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(
        call_tool(server, "req-ref-filter-1", "repo.references", {"symbol": "Api.run", "top_k": 50})
    )

    paths = [item["path"] for item in result["references"]]
    assert all(path == "src/api.ts" for path in paths)
