from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_bundle_exports_written_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def x():\n    return 'x'\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    server.handle_payload({"id": "req-exp-1", "method": "repo.refresh_index", "params": {}})

    response = server.handle_payload(
        {
            "id": "req-exp-2",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "x return",
                "budget": {"max_files": 1, "max_total_lines": 5},
                "strategy": "hybrid",
                "include_tests": True,
            },
        }
    )
    assert response["ok"] is True
    assert response["warnings"] == []
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
    response = server.handle_payload(
        {
            "id": "req-exp-3",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "x return",
                "budget": {"max_files": 1, "max_total_lines": 5},
                "strategy": "hybrid",
                "include_tests": True,
            },
        }
    )

    assert response["ok"] is True
    assert response["blocked"] is False
    assert len(response["warnings"]) >= 1
    assert "last_bundle" in response["warnings"][0]
