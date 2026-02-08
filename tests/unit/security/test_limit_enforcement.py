from __future__ import annotations

import json
from pathlib import Path

from repo_mcp.security import SecurityLimits
from repo_mcp.server import create_server


def test_max_file_bytes_limit_blocks_open_file(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("a" * 20, encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_file_bytes=10))

    response = server.handle_payload(
        {
            "id": "req-large-file",
            "method": "repo.open_file",
            "params": {"path": "large.txt", "start_line": 1, "end_line": 1},
        }
    )

    assert response["blocked"] is True
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "File exceeds max_file_bytes limit.",
    }


def test_max_open_lines_limit_blocks_large_range(tmp_path: Path) -> None:
    target = tmp_path / "many_lines.txt"
    target.write_text("1\n2\n3\n4\n5\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_open_lines=2))

    response = server.handle_payload(
        {
            "id": "req-lines",
            "method": "repo.open_file",
            "params": {"path": "many_lines.txt", "start_line": 1, "end_line": 5},
        }
    )

    assert response["blocked"] is True
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "Requested line range exceeds max_open_lines limit.",
    }


def test_max_search_hits_limit_blocks_large_top_k(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path), limits=SecurityLimits(max_search_hits=3))

    response = server.handle_payload(
        {"id": "req-search", "method": "repo.search", "params": {"query": "x", "top_k": 10}}
    )

    assert response["blocked"] is True
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "Requested top_k exceeds max_search_hits limit.",
    }


def test_max_total_response_bytes_limit_blocks_oversized_payload(tmp_path: Path) -> None:
    target = tmp_path / "lines.txt"
    target.write_text("a\nb\nc\n", encoding="utf-8")
    server = create_server(
        repo_root=str(tmp_path),
        limits=SecurityLimits(max_total_bytes_per_response=120),
    )

    response = server.handle_payload(
        {
            "id": "req-response-size",
            "method": "repo.open_file",
            "params": {"path": "lines.txt", "start_line": 1, "end_line": 3},
        }
    )

    encoded = json.dumps(response, sort_keys=True).encode("utf-8")
    assert response["blocked"] is True
    assert response["error"] == {
        "code": "PATH_BLOCKED",
        "message": "Response exceeds max_total_bytes_per_response limit.",
    }
    assert len(encoded) <= 1200
