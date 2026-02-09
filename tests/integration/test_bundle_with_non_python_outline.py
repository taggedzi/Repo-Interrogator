from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_bundle_uses_non_python_outline_when_available(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "repo_mcp.toml").write_text(
        '[index]\ninclude_extensions = [".ts"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "mod.ts").write_text(
        "export function buildService(name: string) {\n  return name.trim();\n}\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    refreshed = server.handle_payload(
        {"id": "req-bundle-np-1", "method": "repo.refresh_index", "params": {"force": True}}
    )
    assert refreshed["ok"] is True

    response = server.handle_payload(
        {
            "id": "req-bundle-np-2",
            "method": "repo.build_context_bundle",
            "params": {
                "prompt": "buildService",
                "budget": {"max_files": 1, "max_total_lines": 20},
                "strategy": "hybrid",
                "include_tests": True,
            },
        }
    )

    assert response["ok"] is True
    selections = response["result"]["selections"]
    assert len(selections) >= 1
    first = selections[0]
    assert first["path"] == "src/mod.ts"
    assert "aligned_symbol=buildService" in first["rationale"]
