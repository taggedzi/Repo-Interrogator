from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_cross_platform_style_inputs_produce_stable_outputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        "class A:\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "\n"
        "def parse_token(text: str) -> str:\n"
        "    return text\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-cross-1", "method": "repo.refresh_index", "params": {}})

    open_posix = server.handle_payload(
        {
            "id": "req-cross-2",
            "method": "repo.open_file",
            "params": {"path": "src/mod.py", "start_line": 1, "end_line": 5},
        }
    )
    open_windows = server.handle_payload(
        {
            "id": "req-cross-3",
            "method": "repo.open_file",
            "params": {"path": r"src\mod.py", "start_line": 1, "end_line": 5},
        }
    )

    outline_posix = server.handle_payload(
        {"id": "req-cross-4", "method": "repo.outline", "params": {"path": "src/mod.py"}}
    )
    outline_windows = server.handle_payload(
        {"id": "req-cross-5", "method": "repo.outline", "params": {"path": r"src\mod.py"}}
    )

    search_slash = server.handle_payload(
        {
            "id": "req-cross-6",
            "method": "repo.search",
            "params": {"query": "parse token", "mode": "bm25", "top_k": 10, "path_prefix": "src/"},
        }
    )
    search_backslash = server.handle_payload(
        {
            "id": "req-cross-7",
            "method": "repo.search",
            "params": {
                "query": "parse token",
                "mode": "bm25",
                "top_k": 10,
                "path_prefix": r"src\\",
            },
        }
    )

    assert open_posix["ok"] is True
    assert open_windows["ok"] is True
    assert open_posix["result"]["numbered_lines"] == open_windows["result"]["numbered_lines"]

    assert outline_posix["ok"] is True
    assert outline_windows["ok"] is True
    assert outline_posix["result"] == outline_windows["result"]

    assert search_slash["ok"] is True
    assert search_backslash["ok"] is True
    assert search_slash["result"]["hits"] == search_backslash["result"]["hits"]
