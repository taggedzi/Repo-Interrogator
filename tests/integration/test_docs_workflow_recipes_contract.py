from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def _setup_recipe_fixture(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        (
            "class Service:\n"
            "    def run(self, token: str) -> str:\n"
            "        return token.strip().lower()\n"
            "\n"
            "def normalize_token(token: str) -> str:\n"
            "    return Service().run(token)\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "src" / "handlers.py").write_text(
        (
            "from service import Service\n"
            "\n"
            "def handle_request(raw: str) -> str:\n"
            "    service = Service()\n"
            "    return service.run(raw)\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "src" / "api.py").write_text(
        (
            "from handlers import handle_request\n"
            "\n"
            "def api_entry(raw: str) -> str:\n"
            "    return handle_request(raw)\n"
        ),
        encoding="utf-8",
    )


def test_docs_recipe_bug_investigation_contract_fields(tmp_path: Path) -> None:
    _setup_recipe_fixture(tmp_path)
    server = create_server(repo_root=str(tmp_path))

    refreshed = server.handle_payload(
        {"id": "doc-bug-1", "method": "repo.refresh_index", "params": {"force": False}}
    )
    assert refreshed["ok"] is True

    searched = server.handle_payload(
        {
            "id": "doc-bug-2",
            "method": "repo.search",
            "params": {"query": "Service.run token normalize", "mode": "bm25", "top_k": 8},
        }
    )
    assert searched["ok"] is True
    hits = searched["result"]["hits"]
    assert isinstance(hits, list)
    assert hits

    opened = server.handle_payload(
        {
            "id": "doc-bug-3",
            "method": "repo.open_file",
            "params": {"path": "src/service.py", "start_line": 1, "end_line": 40},
        }
    )
    assert opened["ok"] is True
    assert isinstance(opened["result"]["numbered_lines"], list)

    bundled = server.handle_payload(
        {
            "id": "doc-bug-4",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "find likely bug in Service.run and nearby call flow",
                "budget": {"max_files": 3, "max_total_lines": 120},
                "strategy": "hybrid",
                "include_tests": False,
            },
        }
    )
    assert bundled["ok"] is True
    result = bundled["result"]
    assert isinstance(result["selections"], list)
    assert isinstance(result["citations"], list)
    if result["selections"]:
        assert "why_selected" in result["selections"][0]
    assert "selection_debug" in result["audit"]
    summary = result["audit"]["selection_debug"]["why_not_selected_summary"]
    assert set(summary.keys()) == {"total_skipped_candidates", "reason_counts", "top_skipped"}


def test_docs_recipe_refactor_impact_contract_fields(tmp_path: Path) -> None:
    _setup_recipe_fixture(tmp_path)
    server = create_server(repo_root=str(tmp_path))

    outlined = server.handle_payload(
        {"id": "doc-ref-1", "method": "repo.outline", "params": {"path": "src/service.py"}}
    )
    assert outlined["ok"] is True
    assert isinstance(outlined["result"]["symbols"], list)

    references = server.handle_payload(
        {
            "id": "doc-ref-2",
            "method": "repo.references",
            "params": {"symbol": "Service.run", "top_k": 50},
        }
    )
    assert references["ok"] is True
    refs = references["result"]["references"]
    assert isinstance(refs, list)
    assert refs
    sample = refs[0]
    assert {"path", "line", "strategy", "confidence"}.issubset(set(sample.keys()))

    scoped = server.handle_payload(
        {
            "id": "doc-ref-3",
            "method": "repo.references",
            "params": {"symbol": "Service.run", "path": "src/handlers.py", "top_k": 50},
        }
    )
    assert scoped["ok"] is True
    scoped_refs = scoped["result"]["references"]
    assert isinstance(scoped_refs, list)
    if scoped_refs:
        assert {item["path"] for item in scoped_refs} == {"src/handlers.py"}


def test_docs_recipe_data_flow_tracing_contract_fields(tmp_path: Path) -> None:
    _setup_recipe_fixture(tmp_path)
    server = create_server(repo_root=str(tmp_path))

    searched = server.handle_payload(
        {
            "id": "doc-flow-1",
            "method": "repo.search",
            "params": {
                "query": "handle_request api_entry Service.run",
                "mode": "bm25",
                "top_k": 10,
            },
        }
    )
    assert searched["ok"] is True
    assert isinstance(searched["result"]["hits"], list)

    references = server.handle_payload(
        {
            "id": "doc-flow-2",
            "method": "repo.references",
            "params": {"symbol": "handle_request", "top_k": 50},
        }
    )
    assert references["ok"] is True
    assert isinstance(references["result"]["references"], list)

    bundled = server.handle_payload(
        {
            "id": "doc-flow-3",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "trace request flow from api entrypoint through handlers into service",
                "budget": {"max_files": 5, "max_total_lines": 180},
                "strategy": "hybrid",
                "include_tests": False,
            },
        }
    )
    assert bundled["ok"] is True
    result = bundled["result"]
    ranking_debug = result["audit"]["ranking_debug"]
    selection_debug = result["audit"]["selection_debug"]
    assert isinstance(ranking_debug["top_candidates"], list)
    assert isinstance(
        selection_debug["why_not_selected_summary"]["top_skipped"],
        list,
    )
    assert set(result["totals"].keys()) == {"selected_files", "selected_lines", "truncated"}
    assert isinstance(result["citations"], list)
