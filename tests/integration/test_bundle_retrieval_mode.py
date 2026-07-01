from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error

from repo_mcp.server import create_server


def test_bundle_default_retrieval_mode_is_bm25_and_unaffected(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-1",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )
    assert not is_tool_error(response)


def test_bundle_semantic_retrieval_mode_without_extra_returns_explicit_error(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-2",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
            "retrieval_mode": "semantic",
        },
    )
    assert is_tool_error(response)


def test_bundle_rejects_invalid_retrieval_mode(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-3",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
            "retrieval_mode": "not-a-real-mode",
        },
    )
    assert is_tool_error(response)
