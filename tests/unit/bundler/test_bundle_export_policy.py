from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, is_tool_error

from repo_mcp.server import create_server


def test_bundle_exports_written_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def x():\n    return 'x'\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-exp-1", "repo.refresh_index", {})

    response = call_tool(
        server,
        "req-exp-2",
        "repo.build_context_bundle",
        {
            "prompt": "x return",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    assert not is_tool_error(response)
    content = response["result"]["content"]
    assert len(content) == 1  # no warnings
    assert (tmp_path / ".repo_mcp" / "last_bundle.json").exists()
    assert (tmp_path / ".repo_mcp" / "last_bundle.md").exists()


def test_bundle_export_failure_returns_warning_but_success(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def x():\n    return 'x'\n", encoding="utf-8")
    data_dir = tmp_path / ".repo_mcp"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "last_bundle.json").mkdir()
    (data_dir / "last_bundle.md").mkdir()
    server = create_server(repo_root=str(tmp_path))
    response = call_tool(
        server,
        "req-exp-3",
        "repo.build_context_bundle",
        {
            "prompt": "x return",
            "budget": {"max_files": 1, "max_total_lines": 5},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )

    assert not is_tool_error(response)
    content = response["result"]["content"]
    assert len(content) >= 2  # result + at least one warning
    warning_texts = [item["text"] for item in content[1:]]
    assert any("last_bundle" in w for w in warning_texts)
