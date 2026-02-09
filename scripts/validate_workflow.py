#!/usr/bin/env python3
"""Run and validate the full Repo Interrogator workflow over STDIO."""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_ENVELOPE_KEYS = {"request_id", "ok", "result", "warnings", "blocked"}
DEFAULT_RESPONSE_TIMEOUT_SECONDS = 180.0


@dataclass(slots=True)
class CheckResult:
    """Single validation result."""

    name: str
    ok: bool
    details: str
    expected: str | None = None
    actual: str | None = None


class WorkflowValidator:
    """Execute requests and validate workflow behavior."""

    def __init__(
        self,
        repo_root: Path,
        data_dir: Path | None,
        verbose: bool,
        response_timeout_seconds: float,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.data_dir = data_dir.resolve() if data_dir is not None else None
        self.verbose = verbose
        self.response_timeout_seconds = response_timeout_seconds
        self.proc: subprocess.Popen[str] | None = None
        self.results: list[CheckResult] = []

    def run(self) -> int:
        self._start_server()
        try:
            self._step_status()
            self._step_refresh()
            search_response = self._step_search()
            opened_path = self._step_open(search_response)
            self._step_outline(opened_path)
            self._step_bundle()
            self._step_audit()
        except Exception as error:  # pragma: no cover
            self.results.append(
                CheckResult(
                    name="workflow.runtime",
                    ok=False,
                    details=f"Unhandled runtime error during workflow: {error}",
                )
            )
        finally:
            self._stop_server()

        self._print_summary()
        return 0 if all(result.ok for result in self.results) else 1

    def _start_server(self) -> None:
        env = os.environ.copy()
        workspace_src = Path(__file__).resolve().parents[1] / "src"
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(workspace_src)
            if not existing_pythonpath
            else f"{workspace_src}:{existing_pythonpath}"
        )

        cmd = [sys.executable, "-m", "repo_mcp.server", "--repo-root", str(self.repo_root)]
        if self.data_dir is not None:
            cmd.extend(["--data-dir", str(self.data_dir)])

        print(f"$ {' '.join(cmd)}")
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _stop_server(self) -> None:
        if self.proc is None:
            return
        proc = self.proc
        self.proc = None
        if proc.stdin is not None:
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("Server process is not running.")

        print(f">>> {json.dumps(request, sort_keys=True)}")
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()

        stdout_fd = self.proc.stdout.fileno()
        ready, _, _ = select.select([stdout_fd], [], [], self.response_timeout_seconds)
        if not ready:
            raise RuntimeError(
                f"Timed out after {self.response_timeout_seconds:.0f}s waiting for response."
            )
        line = self.proc.stdout.readline()
        if not line:
            stderr_out = ""
            if self.proc.stderr is not None:
                stderr_out = self.proc.stderr.read()
            raise RuntimeError(f"No response from server. stderr={stderr_out}")
        response = json.loads(line)
        print(f"<<< {json.dumps(response, sort_keys=True)}")
        return response

    def _validate_envelope(self, request_id: str, response: dict[str, Any], name: str) -> None:
        keys = set(response.keys())
        if not REQUIRED_ENVELOPE_KEYS.issubset(keys):
            self.results.append(
                CheckResult(
                    name=name,
                    ok=False,
                    details="Response envelope missing required keys.",
                    expected=f"keys include {sorted(REQUIRED_ENVELOPE_KEYS)}",
                    actual=f"keys were {sorted(keys)}",
                )
            )
            return
        if response.get("request_id") != request_id:
            self.results.append(
                CheckResult(
                    name=name,
                    ok=False,
                    details="request_id mismatch in response.",
                    expected=f"request_id={request_id}",
                    actual=f"request_id={response.get('request_id')}",
                )
            )
            return
        self.results.append(CheckResult(name=name, ok=True, details="Envelope is valid."))

    def _assert_true(
        self,
        name: str,
        condition: bool,
        details: str,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self.results.append(
            CheckResult(
                name=name,
                ok=condition,
                details=details if condition else f"FAILED: {details}",
                expected=expected if not condition else None,
                actual=actual if not condition else None,
            )
        )

    @staticmethod
    def _result_keys(value: object) -> str:
        if isinstance(value, dict):
            return f"result keys={sorted(value.keys())}"
        return f"result type={type(value).__name__}"

    def _step_status(self) -> None:
        req_id = "wf-1-status"
        response = self._call({"id": req_id, "method": "repo.status", "params": {}})
        self._validate_envelope(req_id, response, "status.envelope")
        result = response.get("result", {})
        self._assert_true(
            "status.ok",
            response.get("ok") is True,
            "repo.status should return ok=true.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "status.fields",
            isinstance(result, dict)
            and {"repo_root", "index_status", "limits_summary", "effective_config"}.issubset(
                set(result.keys())
            ),
            "repo.status should include core fields.",
            expected="result contains repo_root/index_status/limits_summary/effective_config",
            actual=self._result_keys(result),
        )

    def _step_refresh(self) -> None:
        req_id = "wf-2-refresh"
        response = self._call(
            {"id": req_id, "method": "repo.refresh_index", "params": {"force": False}}
        )
        self._validate_envelope(req_id, response, "refresh.envelope")
        result = response.get("result", {})
        self._assert_true(
            "refresh.ok",
            response.get("ok") is True,
            "repo.refresh_index should return ok=true.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "refresh.fields",
            isinstance(result, dict)
            and {"added", "updated", "removed", "duration_ms", "timestamp"}.issubset(
                set(result.keys())
            ),
            "repo.refresh_index should include expected fields.",
            expected="result has added/updated/removed/duration_ms/timestamp",
            actual=self._result_keys(result),
        )

    def _step_search(self) -> dict[str, Any]:
        req_id = "wf-3-search"
        response = self._call(
            {
                "id": req_id,
                "method": "repo.search",
                "params": {
                    "query": "stdio server request routing",
                    "mode": "bm25",
                    "top_k": 5,
                    "path_prefix": "src/",
                },
            }
        )
        self._validate_envelope(req_id, response, "search.envelope")
        hits = response.get("result", {}).get("hits", [])
        self._assert_true(
            "search.ok",
            response.get("ok") is True,
            "repo.search should return ok=true.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "search.hits_type",
            isinstance(hits, list),
            "repo.search result.hits should be a list.",
            expected="hits is list",
            actual=f"hits type={type(hits).__name__}",
        )
        return response

    def _pick_open_path(self, search_response: dict[str, Any]) -> str:
        hits = search_response.get("result", {}).get("hits", [])
        if isinstance(hits, list):
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                path = hit.get("path")
                if not isinstance(path, str):
                    continue
                if path.startswith(".") or not path.endswith(".py"):
                    continue
                return path
        return "src/repo_mcp/server.py"

    def _step_open(self, search_response: dict[str, Any]) -> str:
        path = self._pick_open_path(search_response)
        req_id = "wf-4-open"
        response = self._call(
            {
                "id": req_id,
                "method": "repo.open_file",
                "params": {"path": path, "start_line": 1, "end_line": 20},
            }
        )
        self._validate_envelope(req_id, response, "open.envelope")
        result = response.get("result", {})
        self._assert_true(
            "open.ok",
            response.get("ok") is True,
            "repo.open_file should return ok=true for readable file.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "open.fields",
            isinstance(result, dict) and {"path", "numbered_lines", "truncated"}.issubset(result),
            "repo.open_file should include expected result fields.",
            expected="result has path/numbered_lines/truncated",
            actual=self._result_keys(result),
        )
        return path

    def _step_outline(self, opened_path: str) -> None:
        outline_target = opened_path if opened_path.endswith(".py") else "src/repo_mcp/server.py"
        req_id = "wf-5-outline"
        response = self._call(
            {"id": req_id, "method": "repo.outline", "params": {"path": outline_target}}
        )
        self._validate_envelope(req_id, response, "outline.envelope")
        result = response.get("result", {})
        self._assert_true(
            "outline.ok",
            response.get("ok") is True,
            "repo.outline should return ok=true for readable file.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "outline.fields",
            isinstance(result, dict) and {"path", "language", "symbols"}.issubset(result),
            "repo.outline should include expected result fields.",
            expected="result has path/language/symbols",
            actual=self._result_keys(result),
        )
        symbols = result.get("symbols")
        self._assert_true(
            "outline.symbols_type",
            isinstance(symbols, list),
            "repo.outline result.symbols should be a list.",
            expected="symbols is list",
            actual=f"symbols type={type(symbols).__name__}",
        )
        if not isinstance(symbols, list):
            return

        required_symbol_keys = {
            "kind",
            "name",
            "signature",
            "start_line",
            "end_line",
            "doc",
            "parent_symbol",
            "scope_kind",
            "is_conditional",
            "decl_context",
        }
        symbols_have_v2_shape = True
        invalid_scope_values: list[str] = []
        missing_parent_for_class_scope = 0

        for symbol in symbols:
            if not isinstance(symbol, dict):
                symbols_have_v2_shape = False
                continue
            if not required_symbol_keys.issubset(symbol.keys()):
                symbols_have_v2_shape = False
                continue

            scope_kind = symbol.get("scope_kind")
            if scope_kind not in {None, "module", "class", "function"}:
                invalid_scope_values.append(str(scope_kind))
            if scope_kind == "class" and symbol.get("parent_symbol") is None:
                missing_parent_for_class_scope += 1

        self._assert_true(
            "outline.v2_symbol_fields",
            symbols_have_v2_shape,
            "repo.outline symbols should include v2 metadata fields.",
            expected=f"every symbol has keys {sorted(required_symbol_keys)}",
            actual=f"symbols_count={len(symbols)}",
        )
        self._assert_true(
            "outline.scope_kind_values",
            not invalid_scope_values,
            "repo.outline symbol scope_kind values should be valid when present.",
            expected="scope_kind is one of null/module/class/function",
            actual=f"invalid values={sorted(set(invalid_scope_values))}",
        )
        self._assert_true(
            "outline.class_parent_consistency",
            missing_parent_for_class_scope == 0,
            "Class-scope symbols should provide parent_symbol.",
            expected="class-scope symbols have non-null parent_symbol",
            actual=f"missing_parent_count={missing_parent_for_class_scope}",
        )

    def _step_bundle(self) -> None:
        req_id = "wf-6-bundle"
        response = self._call(
            {
                "id": req_id,
                "method": "repo.build_context_bundle",
                "params": {
                    "prompt": "server request handling and search flow",
                    "budget": {"max_files": 2, "max_total_lines": 80},
                    "strategy": "hybrid",
                    "include_tests": False,
                },
            }
        )
        self._validate_envelope(req_id, response, "bundle.envelope")
        result = response.get("result", {})
        expected_keys = {
            "bundle_id",
            "prompt_fingerprint",
            "strategy",
            "budget",
            "totals",
            "selections",
            "citations",
            "audit",
        }
        self._assert_true(
            "bundle.ok",
            response.get("ok") is True,
            "repo.build_context_bundle should return ok=true.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "bundle.fields",
            isinstance(result, dict) and expected_keys.issubset(result),
            "Bundle result should include required top-level fields.",
            expected=f"result has {sorted(expected_keys)}",
            actual=self._result_keys(result),
        )

    def _step_audit(self) -> None:
        req_id = "wf-7-audit"
        response = self._call({"id": req_id, "method": "repo.audit_log", "params": {"limit": 50}})
        self._validate_envelope(req_id, response, "audit.envelope")
        entries = response.get("result", {}).get("entries", [])
        self._assert_true(
            "audit.ok",
            response.get("ok") is True,
            "repo.audit_log should return ok=true.",
            expected="ok=true",
            actual=f"ok={response.get('ok')}",
        )
        self._assert_true(
            "audit.entries_type",
            isinstance(entries, list),
            "repo.audit_log result.entries should be a list.",
            expected="entries is list",
            actual=f"entries type={type(entries).__name__}",
        )
        expected_tools = {
            "repo.status",
            "repo.refresh_index",
            "repo.search",
            "repo.open_file",
            "repo.outline",
            "repo.build_context_bundle",
        }
        seen_tools = set()
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    tool_name = entry.get("tool")
                    if isinstance(tool_name, str):
                        seen_tools.add(tool_name)
        missing = sorted(expected_tools - seen_tools)
        self._assert_true(
            "audit.tool_coverage",
            not missing,
            "Audit log should include prior workflow tool calls.",
            expected=f"contains tools {sorted(expected_tools)}",
            actual=f"missing={missing}, seen={sorted(seen_tools)}",
        )

    def _print_summary(self) -> None:
        print("\n=== Validation Summary ===")
        for result in self.results:
            status = "PASS" if result.ok else "FAIL"
            print(f"[{status}] {result.name}: {result.details}")
            if not result.ok:
                if result.expected is not None:
                    print(f"  expected: {result.expected}")
                if result.actual is not None:
                    print(f"  actual:   {result.actual}")

        passed = sum(1 for item in self.results if item.ok)
        failed = len(self.results) - passed
        print(f"\nTotal checks: {len(self.results)} | Passed: {passed} | Failed: {failed}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to interrogate. Defaults to current directory.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Optional data directory override passed to repo_mcp.server.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Reserved flag for future expanded output. Current script is already verbose.",
    )
    parser.add_argument(
        "--response-timeout-seconds",
        type=float,
        default=DEFAULT_RESPONSE_TIMEOUT_SECONDS,
        help=(
            "Max seconds to wait for each tool response before marking the workflow failed. "
            f"Default: {DEFAULT_RESPONSE_TIMEOUT_SECONDS:.0f}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validator = WorkflowValidator(
        repo_root=Path(args.repo_root),
        data_dir=Path(args.data_dir) if args.data_dir else None,
        verbose=args.verbose,
        response_timeout_seconds=args.response_timeout_seconds,
    )
    return validator.run()


if __name__ == "__main__":
    raise SystemExit(main())
