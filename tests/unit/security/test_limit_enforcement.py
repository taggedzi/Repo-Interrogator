from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import call_tool, is_tool_error, tool_error_text

from repo_mcp.security import SecurityLimits
from repo_mcp.server import create_server


def test_max_file_bytes_limit_blocks_open_file(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("a" * 20, encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_file_bytes=10))

    response = call_tool(
        server,
        "req-large-file",
        "repo.open_file",
        {"path": "large.txt", "start_line": 1, "end_line": 1},
    )

    assert is_tool_error(response)
    assert "max_file_bytes" in tool_error_text(response).lower() or "Blocked" in tool_error_text(
        response
    )


def test_max_open_lines_limit_blocks_large_range(tmp_path: Path) -> None:
    target = tmp_path / "many_lines.txt"
    target.write_text("1\n2\n3\n4\n5\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_open_lines=2))

    response = call_tool(
        server,
        "req-lines",
        "repo.open_file",
        {"path": "many_lines.txt", "start_line": 1, "end_line": 5},
    )

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)


def test_max_search_hits_limit_blocks_large_top_k(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_search_hits=3))

    response = call_tool(server, "req-search", "repo.search", {"query": "x", "top_k": 10})

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)


def test_max_total_response_bytes_limit_blocks_oversized_payload(tmp_path: Path) -> None:
    target = tmp_path / "lines.txt"
    target.write_text("a\nb\nc\n", encoding="utf-8")
    server = create_server(
        repo_root=str(tmp_path),
        limits=SecurityLimits(max_total_bytes_per_response=120),
    )

    response = call_tool(
        server,
        "req-response-size",
        "repo.open_file",
        {"path": "lines.txt", "start_line": 1, "end_line": 3},
    )

    encoded = json.dumps(response, sort_keys=True).encode("utf-8")
    assert is_tool_error(response)
    assert (
        "max_total_bytes_per_response" in tool_error_text(response).lower()
        or "exceeds" in tool_error_text(response).lower()
    )
    assert len(encoded) <= 1200


def test_max_references_limit_blocks_large_reference_top_k(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_references=2))

    response = call_tool(
        server, "req-references", "repo.references", {"symbol": "Service.run", "top_k": 10}
    )

    assert is_tool_error(response)
    assert "Blocked" in tool_error_text(response)
