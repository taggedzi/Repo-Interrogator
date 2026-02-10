from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def test_stdio_workflow_e2e(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "class App:\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "\n"
        "def parse_token(text: str) -> str:\n"
        "    return text.strip()\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text("token parser workflow\n", encoding="utf-8")

    proc = _start_server(repo_root=tmp_path)
    try:
        status = _call_tool(proc, "req-e2e-1", "repo.status", {})
        assert status["ok"] is True
        assert status["result"]["index_status"] == "not_indexed"

        refreshed = _call_tool(proc, "req-e2e-2", "repo.refresh_index", {"force": False})
        assert refreshed["ok"] is True
        assert refreshed["result"]["added"] == 2

        listed = _call_tool(proc, "req-e2e-3", "repo.list_files", {"max_results": 10})
        assert listed["ok"] is True
        assert [entry["path"] for entry in listed["result"]["files"]] == [
            "docs/guide.md",
            "src/app.py",
        ]

        opened = _call_tool(
            proc,
            "req-e2e-4",
            "repo.open_file",
            {"path": "src/app.py", "start_line": 1, "end_line": 3},
        )
        assert opened["ok"] is True
        assert opened["result"]["path"] == "src/app.py"
        assert len(opened["result"]["numbered_lines"]) == 3

        search_first = _call_tool(
            proc,
            "req-e2e-5",
            "repo.search",
            {"query": "token parser", "mode": "bm25", "top_k": 5},
        )
        search_second = _call_tool(
            proc,
            "req-e2e-6",
            "repo.search",
            {"query": "token parser", "mode": "bm25", "top_k": 5},
        )
        assert search_first["ok"] is True
        assert search_second["ok"] is True
        assert search_first["result"]["hits"] == search_second["result"]["hits"]

        outlined = _call_tool(proc, "req-e2e-7", "repo.outline", {"path": "src/app.py"})
        assert outlined["ok"] is True
        assert outlined["result"]["language"] == "python"
        assert [s["name"] for s in outlined["result"]["symbols"]] == [
            "App",
            "App.run",
            "parse_token",
        ]

        references = _call_tool(
            proc,
            "req-e2e-8",
            "repo.references",
            {"symbol": "App.run", "top_k": 5},
        )
        assert references["ok"] is True
        assert set(references["result"].keys()) == {
            "symbol",
            "references",
            "truncated",
            "total_candidates",
        }

        bundled = _call_tool(
            proc,
            "req-e2e-9",
            "repo.build_context_bundle",
            {
                "prompt": "token parser",
                "budget": {"max_files": 2, "max_total_lines": 20},
                "strategy": "hybrid",
                "include_tests": True,
            },
        )
        assert bundled["ok"] is True
        assert bundled["result"]["totals"]["selected_files"] >= 1

        audit = _call_tool(proc, "req-e2e-10", "repo.audit_log", {"limit": 20})
        assert audit["ok"] is True
        tools = [entry["tool"] for entry in audit["result"]["entries"]]
        assert "repo.build_context_bundle" in tools
        assert "repo.references" in tools
        assert "repo.search" in tools
    finally:
        _stop_server(proc)


def _start_server(repo_root: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    workspace_root = Path(__file__).resolve().parents[2]
    src_path = workspace_root / "src"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(src_path) if not existing else f"{src_path}:{existing}"
    cmd = [
        sys.executable,
        "-m",
        "repo_mcp.server",
        "--repo-root",
        str(repo_root),
        "--data-dir",
        str(repo_root / ".repo_mcp"),
    ]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _call_tool(
    proc: subprocess.Popen[str],
    request_id: str,
    method: str,
    params: dict[str, object],
) -> dict[str, Any]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    payload = {"id": request_id, "method": method, "params": params}
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr_output = ""
        if proc.stderr is not None:
            stderr_output = proc.stderr.read()
        raise RuntimeError(f"Server produced no response. stderr={stderr_output}")
    return json.loads(line)


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None:
        proc.stdin.close()
    proc.wait(timeout=5)
    if proc.returncode != 0 and proc.stderr is not None:
        stderr_output = proc.stderr.read()
        raise AssertionError(f"Server exited with code {proc.returncode}: {stderr_output}")
