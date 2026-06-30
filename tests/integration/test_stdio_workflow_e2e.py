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
        # MCP handshake
        init_resp = _send(
            proc,
            {
                "id": 0,
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e", "version": "0"},
                },
            },
        )
        assert init_resp["result"]["protocolVersion"] == "2024-11-05"
        _send_notification(
            proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )

        status = _extract(_call_tool(proc, "req-e2e-1", "repo.status", {}))
        assert status["index_status"] == "not_indexed"

        refreshed = _extract(_call_tool(proc, "req-e2e-2", "repo.refresh_index", {"force": False}))
        assert refreshed["added"] == 2

        listed = _extract(_call_tool(proc, "req-e2e-3", "repo.list_files", {"max_results": 10}))
        assert [entry["path"] for entry in listed["files"]] == [
            "docs/guide.md",
            "src/app.py",
        ]

        opened = _extract(
            _call_tool(
                proc,
                "req-e2e-4",
                "repo.open_file",
                {"path": "src/app.py", "start_line": 1, "end_line": 3},
            )
        )
        assert opened["path"] == "src/app.py"
        assert len(opened["numbered_lines"]) == 3

        search_first = _extract(
            _call_tool(
                proc,
                "req-e2e-5",
                "repo.search",
                {"query": "token parser", "mode": "bm25", "top_k": 5},
            )
        )
        search_second = _extract(
            _call_tool(
                proc,
                "req-e2e-6",
                "repo.search",
                {"query": "token parser", "mode": "bm25", "top_k": 5},
            )
        )
        assert search_first["hits"] == search_second["hits"]

        outlined = _extract(_call_tool(proc, "req-e2e-7", "repo.outline", {"path": "src/app.py"}))
        assert outlined["language"] == "python"
        assert [s["name"] for s in outlined["symbols"]] == ["App", "App.run", "parse_token"]

        references = _extract(
            _call_tool(proc, "req-e2e-8", "repo.references", {"symbol": "App.run", "top_k": 5})
        )
        assert set(references.keys()) == {"symbol", "references", "truncated", "total_candidates"}

        bundled = _extract(
            _call_tool(
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
        )
        assert bundled["totals"]["selected_files"] >= 1

        audit = _extract(_call_tool(proc, "req-e2e-10", "repo.audit_log", {"limit": 20}))
        tools = [entry["tool"] for entry in audit["entries"]]
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


def _send(proc: subprocess.Popen[str], payload: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON-RPC 2.0 request and read the response."""
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr_output = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"Server produced no response. stderr={stderr_output}")
    return json.loads(line)


def _send_notification(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    """Send a notification (no response expected)."""
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def _call_tool(
    proc: subprocess.Popen[str],
    request_id: str,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, Any]:
    """Send a tools/call request and return the full JSON-RPC 2.0 response."""
    return _send(
        proc,
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    )


def _extract(response: dict[str, Any]) -> dict[str, Any]:
    """Extract the tool result dict from a successful tools/call response."""
    assert "error" not in response, f"JSON-RPC error: {response}"
    result = response["result"]
    assert not result.get("isError"), f"Tool error: {result['content'][0]['text']}"
    return json.loads(result["content"][0]["text"])


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None:
        proc.stdin.close()
    proc.wait(timeout=5)
    if proc.returncode != 0 and proc.stderr is not None:
        stderr_output = proc.stderr.read()
        raise AssertionError(f"Server exited with code {proc.returncode}: {stderr_output}")
