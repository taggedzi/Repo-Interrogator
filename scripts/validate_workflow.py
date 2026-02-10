#!/usr/bin/env python3
"""Run and validate the full Repo Interrogator workflow over STDIO."""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import platform
import pstats
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
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


@dataclass(slots=True)
class StepTiming:
    """Timing record for one workflow step."""

    name: str
    elapsed_seconds: float
    ok: bool
    error: str | None = None


class WorkflowValidator:
    """Execute requests and validate workflow behavior."""

    def __init__(
        self,
        repo_root: Path,
        data_dir: Path | None,
        verbose: bool,
        response_timeout_seconds: float,
        profile_enabled: bool,
        profile_output_path: Path | None,
        profile_references: bool,
        profile_bundler: bool,
        server_cprofile_output: Path | None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.data_dir = data_dir.resolve() if data_dir is not None else None
        self.verbose = verbose
        self.response_timeout_seconds = response_timeout_seconds
        self.profile_enabled = profile_enabled
        self.profile_output_path = profile_output_path
        self.profile_references = profile_references
        self.profile_bundler = profile_bundler
        self.server_cprofile_output = server_cprofile_output
        self.proc: subprocess.Popen[str] | None = None
        self.results: list[CheckResult] = []
        self.step_timings: list[StepTiming] = []
        self.started_at_utc = datetime.now(UTC)
        self.total_elapsed_seconds = 0.0

    def run(self) -> int:
        start = time.perf_counter()
        self._start_server()
        try:
            self._run_step("repo.status", self._step_status)
            self._run_step("repo.refresh_index", self._step_refresh)
            search_response = self._run_step("repo.search", self._step_search)
            opened_path = self._run_step("repo.open_file", self._step_open, search_response)
            symbol = self._run_step("repo.outline", self._step_outline, opened_path)
            self._run_step("repo.references", self._step_references, symbol)
            self._run_step("repo.build_context_bundle", self._step_bundle)
            self._run_step("repo.audit_log", self._step_audit)
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
            self.total_elapsed_seconds = time.perf_counter() - start

        self._print_summary()
        self._print_profile_summary()
        self._write_profile_output()
        return 0 if all(result.ok for result in self.results) else 1

    def _run_step(self, name: str, step: Any, *args: Any) -> Any:
        started = time.perf_counter()
        try:
            result = step(*args)
        except Exception as error:
            self.step_timings.append(
                StepTiming(
                    name=name,
                    elapsed_seconds=time.perf_counter() - started,
                    ok=False,
                    error=str(error),
                )
            )
            raise
        self.step_timings.append(
            StepTiming(
                name=name,
                elapsed_seconds=time.perf_counter() - started,
                ok=True,
            )
        )
        return result

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
        if self.profile_references:
            env["REPO_MCP_PROFILE_REFERENCES"] = "1"
        if self.profile_bundler:
            env["REPO_MCP_PROFILE_BUNDLER"] = "1"
        if self.server_cprofile_output is not None:
            env["REPO_MCP_SERVER_CPROFILE_OUTPUT"] = str(self.server_cprofile_output)

        print(f"$ {' '.join(cmd)}")
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
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
            raise RuntimeError("No response from server.")
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
            and {
                "repo_root",
                "index_status",
                "limits_summary",
                "effective_config",
            }.issubset(set(result.keys())),
            "repo.status should include core fields.",
            expected="result contains repo_root/index_status/limits_summary/effective_config",
            actual=self._result_keys(result),
        )
        limits_summary = result.get("limits_summary", {})
        limits_summary_keys = (
            sorted(limits_summary.keys())
            if isinstance(limits_summary, dict)
            else type(limits_summary).__name__
        )
        self._assert_true(
            "status.max_references_limit",
            isinstance(limits_summary, dict) and "max_references" in limits_summary,
            "repo.status limits_summary should include max_references.",
            expected="limits_summary has max_references",
            actual=f"limits_summary keys={limits_summary_keys}",
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

    def _step_outline(self, opened_path: str) -> str:
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
        chosen_symbol = "StdioServer.handle_payload"
        if isinstance(symbols, list):
            preferred_symbols = (
                "StdioServer.handle_payload",
                "StdioServer.parse_request",
                "StdioServer.handle_json_line",
                "StdioServer.serve",
            )
            available_symbols = {
                symbol.get("name")
                for symbol in symbols
                if isinstance(symbol, dict) and isinstance(symbol.get("name"), str)
            }
            for preferred in preferred_symbols:
                if preferred in available_symbols:
                    return preferred
            fallback_symbol: str | None = None
            for symbol in symbols:
                if not isinstance(symbol, dict):
                    continue
                name = symbol.get("name")
                if isinstance(name, str) and name.strip():
                    if "." in name:
                        chosen_symbol = name
                        break
                    if fallback_symbol is None:
                        fallback_symbol = name
            if chosen_symbol == "StdioServer.handle_payload" and fallback_symbol:
                chosen_symbol = fallback_symbol
        return chosen_symbol

    def _step_references(self, symbol: str) -> None:
        req_id_first = "wf-6-references-1"
        req_id_second = "wf-6-references-2"
        first = self._call(
            {
                "id": req_id_first,
                "method": "repo.references",
                "params": {
                    "symbol": symbol,
                    "path": "src/repo_mcp/server.py",
                    "top_k": 10,
                },
            }
        )
        second = self._call(
            {
                "id": req_id_second,
                "method": "repo.references",
                "params": {
                    "symbol": symbol,
                    "path": "src/repo_mcp/server.py",
                    "top_k": 10,
                },
            }
        )
        self._validate_envelope(req_id_first, first, "references.envelope.first")
        self._validate_envelope(req_id_second, second, "references.envelope.second")
        self._assert_true(
            "references.ok.first",
            first.get("ok") is True,
            "First repo.references call should return ok=true.",
            expected="ok=true",
            actual=f"ok={first.get('ok')}",
        )
        self._assert_true(
            "references.ok.second",
            second.get("ok") is True,
            "Second repo.references call should return ok=true.",
            expected="ok=true",
            actual=f"ok={second.get('ok')}",
        )
        first_result = first.get("result", {})
        second_result = second.get("result", {})
        self._assert_true(
            "references.fields",
            isinstance(first_result, dict)
            and {"symbol", "references", "truncated", "total_candidates"}.issubset(
                set(first_result.keys())
            ),
            "repo.references should include required result fields.",
            expected="result has symbol/references/truncated/total_candidates",
            actual=self._result_keys(first_result),
        )
        self._assert_true(
            "references.deterministic",
            first_result == second_result,
            "repo.references repeated calls should be deterministic.",
            expected="first result equals second result",
            actual="results differ" if first_result != second_result else "results equal",
        )
        references = first_result.get("references", [])
        self._assert_true(
            "references.list_type",
            isinstance(references, list),
            "repo.references result.references should be a list.",
            expected="references is list",
            actual=f"references type={type(references).__name__}",
        )
        if isinstance(references, list) and references:
            sample = references[0]
            sample_keys = (
                sorted(sample.keys()) if isinstance(sample, dict) else type(sample).__name__
            )
            self._assert_true(
                "references.record_shape",
                isinstance(sample, dict)
                and {
                    "symbol",
                    "path",
                    "line",
                    "kind",
                    "evidence",
                    "strategy",
                    "confidence",
                }.issubset(set(sample.keys())),
                "repo.references records should include contract fields.",
                expected=("reference has symbol/path/line/kind/evidence/strategy/confidence"),
                actual=f"sample keys={sample_keys}",
            )

    def _step_bundle(self) -> None:
        req_id = "wf-7-bundle"
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
        selections = result.get("selections", [])
        self._assert_true(
            "bundle.selections_type",
            isinstance(selections, list),
            "Bundle selections should be a list.",
            expected="selections is list",
            actual=f"selections type={type(selections).__name__}",
        )
        if isinstance(selections, list) and selections:
            first = selections[0]
            why_selected = first.get("why_selected") if isinstance(first, dict) else None
            self._assert_true(
                "bundle.why_selected_shape",
                isinstance(why_selected, dict)
                and {
                    "matched_signals",
                    "score_components",
                    "source_query",
                    "matched_terms",
                    "symbol_reference",
                }.issubset(set(why_selected.keys())),
                "Bundle selections should include v2.5 why_selected fields.",
                expected=(
                    "why_selected has matched_signals/score_components/source_query/"
                    "matched_terms/symbol_reference"
                ),
                actual=f"why_selected={type(why_selected).__name__}",
            )
            score_components = (
                why_selected.get("score_components") if isinstance(why_selected, dict) else None
            )
            self._assert_true(
                "bundle.score_components_shape",
                isinstance(score_components, dict)
                and {
                    "search_score",
                    "definition_match",
                    "reference_count_in_range",
                    "min_definition_distance",
                    "path_name_relevance",
                    "range_size_penalty",
                }.issubset(set(score_components.keys())),
                "Bundle why_selected.score_components should include ranking signals.",
                expected=(
                    "score_components has search_score/definition_match/"
                    "reference_count_in_range/min_definition_distance/"
                    "path_name_relevance/range_size_penalty"
                ),
                actual=f"score_components={type(score_components).__name__}",
            )
        audit = result.get("audit", {})
        ranking_debug = audit.get("ranking_debug") if isinstance(audit, dict) else None
        self._assert_true(
            "bundle.ranking_debug_shape",
            isinstance(ranking_debug, dict)
            and {
                "candidate_count",
                "definition_match_count",
                "reference_proximity_count",
                "top_candidates",
            }.issubset(set(ranking_debug.keys())),
            "Bundle audit should include ranking_debug explainability fields.",
            expected=(
                "ranking_debug has candidate_count/definition_match_count/"
                "reference_proximity_count/top_candidates"
            ),
            actual=f"ranking_debug={type(ranking_debug).__name__}",
        )
        if isinstance(ranking_debug, dict):
            top_candidates = ranking_debug.get("top_candidates")
            self._assert_true(
                "bundle.ranking_debug_top_candidates_type",
                isinstance(top_candidates, list),
                "Bundle audit.ranking_debug.top_candidates should be a list.",
                expected="top_candidates is list",
                actual=f"top_candidates type={type(top_candidates).__name__}",
            )
            if isinstance(top_candidates, list) and top_candidates:
                sample = top_candidates[0]
                self._assert_true(
                    "bundle.ranking_debug_candidate_shape",
                    isinstance(sample, dict)
                    and {
                        "path",
                        "start_line",
                        "end_line",
                        "source_query",
                        "selected",
                        "rank_position",
                        "definition_match",
                        "reference_count_in_range",
                        "min_definition_distance",
                        "path_name_relevance",
                        "search_score",
                        "range_size_penalty",
                    }.issubset(set(sample.keys())),
                    "ranking_debug top candidate entries should include debug contract fields.",
                    expected="top candidate has ranking debug keys",
                    actual=f"sample={type(sample).__name__}",
                )
        selection_debug = audit.get("selection_debug") if isinstance(audit, dict) else None
        self._assert_true(
            "bundle.selection_debug_shape",
            isinstance(selection_debug, dict) and {"why_not_selected_summary"}.issubset(
                set(selection_debug.keys())
            ),
            "Bundle audit should include selection_debug explainability fields.",
            expected="selection_debug has why_not_selected_summary",
            actual=f"selection_debug={type(selection_debug).__name__}",
        )
        if isinstance(selection_debug, dict):
            why_not_selected_summary = selection_debug.get("why_not_selected_summary")
            self._assert_true(
                "bundle.why_not_selected_summary_shape",
                isinstance(why_not_selected_summary, dict)
                and {
                    "total_skipped_candidates",
                    "reason_counts",
                    "top_skipped",
                }.issubset(set(why_not_selected_summary.keys())),
                (
                    "Bundle selection_debug.why_not_selected_summary should include"
                    " bounded skip explainability fields."
                ),
                expected=(
                    "why_not_selected_summary has total_skipped_candidates/"
                    "reason_counts/top_skipped"
                ),
                actual=f"why_not_selected_summary={type(why_not_selected_summary).__name__}",
            )
            if isinstance(why_not_selected_summary, dict):
                self._assert_true(
                    "bundle.why_not_selected_reason_counts_type",
                    isinstance(why_not_selected_summary.get("reason_counts"), dict),
                    (
                        "Bundle selection_debug.why_not_selected_summary.reason_counts"
                        " should be a dict."
                    ),
                    expected="reason_counts is dict",
                    actual=(
                        "reason_counts type="
                        f"{type(why_not_selected_summary.get('reason_counts')).__name__}"
                    ),
                )
                top_skipped = why_not_selected_summary.get("top_skipped")
                self._assert_true(
                    "bundle.why_not_selected_top_skipped_type",
                    isinstance(top_skipped, list),
                    (
                        "Bundle selection_debug.why_not_selected_summary.top_skipped"
                        " should be a list."
                    ),
                    expected="top_skipped is list",
                    actual=f"top_skipped type={type(top_skipped).__name__}",
                )
                if isinstance(top_skipped, list) and top_skipped:
                    skipped_sample = top_skipped[0]
                    self._assert_true(
                        "bundle.why_not_selected_top_skipped_shape",
                        isinstance(skipped_sample, dict)
                        and {
                            "path",
                            "start_line",
                            "end_line",
                            "source_query",
                            "reason",
                        }.issubset(set(skipped_sample.keys())),
                        (
                            "why_not_selected top_skipped entries should include"
                            " deterministic skip-debug fields."
                        ),
                        expected="top_skipped item has skip-debug keys",
                        actual=f"sample={type(skipped_sample).__name__}",
                    )

    def _step_audit(self) -> None:
        req_id = "wf-8-audit"
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
            "repo.references",
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

    def _print_profile_summary(self) -> None:
        if not self.profile_enabled:
            return
        print("\n=== Profile Summary ===")
        print(f"Total elapsed seconds: {self.total_elapsed_seconds:.3f}")
        for timing in self.step_timings:
            status = "ok" if timing.ok else "failed"
            suffix = f" error={timing.error}" if timing.error else ""
            print(f"- {timing.name}: {timing.elapsed_seconds:.3f}s ({status}){suffix}")
        snapshot = self._system_snapshot()
        print(
            "System snapshot: "
            f"platform={snapshot['platform']}, "
            f"python={snapshot['python_version']}, "
            f"cpu_count_logical={snapshot['cpu_count_logical']}, "
            f"max_rss_kb={snapshot['max_rss_kb']}"
        )

    def _write_profile_output(self) -> None:
        if not self.profile_enabled or self.profile_output_path is None:
            return
        payload = {
            "started_at_utc": self.started_at_utc.isoformat(),
            "repo_root": str(self.repo_root),
            "total_elapsed_seconds": self.total_elapsed_seconds,
            "steps": [
                {
                    "name": item.name,
                    "elapsed_seconds": item.elapsed_seconds,
                    "ok": item.ok,
                    "error": item.error,
                }
                for item in self.step_timings
            ],
            "system": self._system_snapshot(),
            "summary": {
                "checks_total": len(self.results),
                "checks_passed": sum(1 for item in self.results if item.ok),
                "checks_failed": sum(1 for item in self.results if not item.ok),
            },
        }
        self.profile_output_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"Profile JSON written to {self.profile_output_path}")

    @staticmethod
    def _system_snapshot() -> dict[str, object]:
        max_rss_kb: int | None = None
        try:
            import resource  # type: ignore

            max_rss_kb = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except Exception:  # pragma: no cover - platform dependent
            max_rss_kb = None
        load_avg: list[float] | None = None
        if hasattr(os, "getloadavg"):
            try:
                one, five, fifteen = os.getloadavg()
                load_avg = [one, five, fifteen]
            except OSError:  # pragma: no cover - platform dependent
                load_avg = None
        return {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "cpu_count_logical": os.cpu_count(),
            "max_rss_kb": max_rss_kb,
            "load_avg": load_avg,
            "pid": os.getpid(),
        }


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
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable timing profile summary for workflow steps and environment snapshot.",
    )
    parser.add_argument(
        "--profile-output",
        default=None,
        help="Optional JSON path for profile output (implies --profile).",
    )
    parser.add_argument(
        "--cprofile-output",
        default=None,
        help=(
            "Optional path to write cProfile .pstats for script-level Python profiling. "
            "When omitted, cProfile is disabled."
        ),
    )
    parser.add_argument(
        "--profile-references",
        action="store_true",
        help=(
            "Enable server-side targeted profiling for repo.references candidate discovery "
            "and adapter resolution paths."
        ),
    )
    parser.add_argument(
        "--profile-bundler",
        action="store_true",
        help=(
            "Enable server-side targeted profiling for bundler ranking, dedupe, "
            "and budget enforcement paths."
        ),
    )
    parser.add_argument(
        "--server-cprofile-output",
        default=None,
        help=(
            "Optional path to write server-process cProfile .pstats for internal "
            "CPU hotspot analysis."
        ),
    )
    parser.add_argument(
        "--server-cprofile-top",
        type=int,
        default=20,
        help=(
            "Number of top cumulative functions to print for server cProfile summary. "
            "Default: 20."
        ),
    )
    return parser.parse_args()


def summarize_cprofile(path: Path, top: int) -> list[str]:
    """Build a compact cumulative-time summary from a .pstats artifact."""
    stats = pstats.Stats(str(path))
    entries: list[tuple[float, str]] = []
    for func, (_cc, _nc, _tt, ct, _callers) in stats.stats.items():
        if ct <= 0:
            continue
        filename, lineno, funcname = func
        label = f"{filename}:{lineno}({funcname})"
        entries.append((ct, label))
    entries.sort(key=lambda item: item[0], reverse=True)
    lines = [f"Top {min(top, len(entries))} cumulative server cProfile functions:"]
    for elapsed, label in entries[:top]:
        lines.append(f"- {elapsed:.3f}s {label}")
    return lines


def main() -> int:
    args = parse_args()
    if args.server_cprofile_top < 1:
        raise SystemExit("--server-cprofile-top must be >= 1")
    profile_output = Path(args.profile_output).resolve() if args.profile_output else None
    server_cprofile_output = (
        Path(args.server_cprofile_output).resolve() if args.server_cprofile_output else None
    )
    profile_enabled = bool(args.profile) or profile_output is not None
    validator = WorkflowValidator(
        repo_root=Path(args.repo_root),
        data_dir=Path(args.data_dir) if args.data_dir else None,
        verbose=args.verbose,
        response_timeout_seconds=args.response_timeout_seconds,
        profile_enabled=profile_enabled,
        profile_output_path=profile_output,
        profile_references=bool(args.profile_references),
        profile_bundler=bool(args.profile_bundler),
        server_cprofile_output=server_cprofile_output,
    )
    if args.cprofile_output:
        profiler = cProfile.Profile()
        profiler.enable()
        exit_code = validator.run()
        profiler.disable()
        cprofile_path = Path(args.cprofile_output).resolve()
        cprofile_path.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(cprofile_path))
        print(f"cProfile stats written to {cprofile_path}")
    else:
        exit_code = validator.run()

    if server_cprofile_output is not None:
        if server_cprofile_output.exists():
            print(f"Server cProfile stats written to {server_cprofile_output}")
            for line in summarize_cprofile(
                path=server_cprofile_output,
                top=int(args.server_cprofile_top),
            ):
                print(line)
        else:
            print(f"Server cProfile output not found: {server_cprofile_output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
