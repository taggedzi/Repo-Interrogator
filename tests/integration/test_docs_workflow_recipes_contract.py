from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server
from tests.helpers import call_tool, extract_result, is_tool_error


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

    refreshed = call_tool(server, "doc-bug-1", "repo.refresh_index", {"force": False})
    assert not is_tool_error(refreshed)

    searched = call_tool(
        server,
        "doc-bug-2",
        "repo.search",
        {"query": "Service.run token normalize", "mode": "bm25", "top_k": 8},
    )
    assert not is_tool_error(searched)
    hits = extract_result(searched)["hits"]
    assert isinstance(hits, list)
    assert hits

    opened = call_tool(
        server,
        "doc-bug-3",
        "repo.open_file",
        {"path": "src/service.py", "start_line": 1, "end_line": 40},
    )
    assert not is_tool_error(opened)
    assert isinstance(extract_result(opened)["numbered_lines"], list)

    bundled = call_tool(
        server,
        "doc-bug-4",
        "repo.build_context_bundle",
        {
            "prompt": "find likely bug in Service.run and nearby call flow",
            "budget": {"max_files": 3, "max_total_lines": 120},
            "strategy": "hybrid",
            "include_tests": False,
        },
    )
    assert not is_tool_error(bundled)
    result = extract_result(bundled)
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

    outlined = call_tool(server, "doc-ref-1", "repo.outline", {"path": "src/service.py"})
    assert not is_tool_error(outlined)
    assert isinstance(extract_result(outlined)["symbols"], list)

    references = call_tool(
        server,
        "doc-ref-2",
        "repo.references",
        {"symbol": "Service.run", "top_k": 50},
    )
    assert not is_tool_error(references)
    refs = extract_result(references)["references"]
    assert isinstance(refs, list)
    assert refs
    sample = refs[0]
    assert {"path", "line", "strategy", "confidence"}.issubset(set(sample.keys()))

    scoped = call_tool(
        server,
        "doc-ref-3",
        "repo.references",
        {"symbol": "Service.run", "path": "src/handlers.py", "top_k": 50},
    )
    assert not is_tool_error(scoped)
    scoped_refs = extract_result(scoped)["references"]
    assert isinstance(scoped_refs, list)
    if scoped_refs:
        assert {item["path"] for item in scoped_refs} == {"src/handlers.py"}


def test_docs_recipe_data_flow_tracing_contract_fields(tmp_path: Path) -> None:
    _setup_recipe_fixture(tmp_path)
    server = create_server(repo_root=str(tmp_path))

    searched = call_tool(
        server,
        "doc-flow-1",
        "repo.search",
        {
            "query": "handle_request api_entry Service.run",
            "mode": "bm25",
            "top_k": 10,
        },
    )
    assert not is_tool_error(searched)
    assert isinstance(extract_result(searched)["hits"], list)

    references = call_tool(
        server,
        "doc-flow-2",
        "repo.references",
        {"symbol": "handle_request", "top_k": 50},
    )
    assert not is_tool_error(references)
    assert isinstance(extract_result(references)["references"], list)

    bundled = call_tool(
        server,
        "doc-flow-3",
        "repo.build_context_bundle",
        {
            "prompt": "trace request flow from api entrypoint through handlers into service",
            "budget": {"max_files": 5, "max_total_lines": 180},
            "strategy": "hybrid",
            "include_tests": False,
        },
    )
    assert not is_tool_error(bundled)
    result = extract_result(bundled)
    ranking_debug = result["audit"]["ranking_debug"]
    selection_debug = result["audit"]["selection_debug"]
    assert isinstance(ranking_debug["top_candidates"], list)
    assert isinstance(
        selection_debug["why_not_selected_summary"]["top_skipped"],
        list,
    )
    assert set(result["totals"].keys()) == {"selected_files", "selected_lines", "truncated"}
    assert isinstance(result["citations"], list)
