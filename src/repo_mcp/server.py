"""STDIO MCP server entrypoint."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from repo_mcp.adapters import AdapterRegistry, build_adapter_registry
from repo_mcp.adapters.base import (
    SymbolReference,
    normalize_and_sort_references,
    normalize_and_sort_symbols,
)
from repo_mcp.bundler import BundleBudget, BundleResult, build_context_bundle
from repo_mcp.config import CliOverrides, ServerConfig, load_effective_config
from repo_mcp.index import IndexManager, IndexSchemaUnsupportedError, discover_files
from repo_mcp.logging import AuditEvent, JsonlAuditLogger, sanitize_arguments, utc_timestamp
from repo_mcp.security import (
    PathBlockedError,
    PolicyBlockedError,
    enforce_file_access_policy,
    resolve_repo_path,
)
from repo_mcp.tools.builtin import register_builtin_tools
from repo_mcp.tools.registry import ToolDispatchError, ToolRegistry


@dataclass(slots=True, frozen=True)
class Request:
    """Normalized incoming request."""

    request_id: str
    method: str
    params: dict[str, object]


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for server startup configuration."""
    parser = argparse.ArgumentParser(prog="repo-mcp")
    parser.add_argument("--repo-root", required=False, default=".")
    parser.add_argument("--data-dir", required=False, default=None)
    parser.add_argument("--max-file-bytes", type=int, required=False, default=None)
    parser.add_argument("--max-open-lines", type=int, required=False, default=None)
    parser.add_argument("--max-total-bytes-per-response", type=int, required=False, default=None)
    parser.add_argument("--max-search-hits", type=int, required=False, default=None)
    parser.add_argument("--max-references", type=int, required=False, default=None)
    parser.add_argument(
        "--python-adapter-enabled", choices=("true", "false"), required=False, default=None
    )
    return parser


class StdioServer:
    """Minimal deterministic STDIO server for tool routing."""

    def __init__(
        self,
        config: ServerConfig,
    ) -> None:
        self._repo_root = config.repo_root
        self._limits = config.limits
        self._data_dir = config.data_dir
        self._config = config
        self._adapters: AdapterRegistry = build_adapter_registry(config)
        self._audit_logger = JsonlAuditLogger(path=self._data_dir / "audit.jsonl")
        self._index_manager = IndexManager(
            repo_root=self._repo_root,
            data_dir=self._data_dir,
            index_config=config.index,
        )
        self._registry = ToolRegistry()
        register_builtin_tools(
            self._registry,
            repo_root=self._repo_root,
            limits=self._limits,
            read_audit_entries=self._audit_logger.read,
            list_files=self._list_files,
            refresh_index=self._index_manager.refresh,
            read_index_status=self._index_manager.status,
            search_index=self._index_manager.search,
            outline_path=self._outline_path,
            build_context_bundle=self._build_context_bundle,
            resolve_references=self._resolve_references,
            config=self._config,
        )
        self._fallback_request_counter = 0
        self._reference_profile_enabled = os.getenv(
            "REPO_MCP_PROFILE_REFERENCES", ""
        ).strip().lower() in {"1", "true", "yes"}
        self._reference_profile_path = self._data_dir / "perf" / "references_profile.jsonl"
        self._reference_profile_sequence = 0
        self._bundler_profile_enabled = os.getenv(
            "REPO_MCP_PROFILE_BUNDLER", ""
        ).strip().lower() in {"1", "true", "yes"}
        self._bundler_profile_path = self._data_dir / "perf" / "bundler_profile.jsonl"
        self._bundler_profile_sequence = 0

    def serve(self, in_stream: TextIO, out_stream: TextIO) -> None:
        """Process JSON-line requests from stdin and write JSON-line responses."""
        for raw_line in in_stream:
            line = raw_line.strip()
            if not line:
                continue
            response = self.handle_json_line(line)
            out_stream.write(f"{json.dumps(response, sort_keys=True)}\n")
            out_stream.flush()

    def handle_json_line(self, raw_line: str) -> dict[str, object]:
        """Handle a single JSON-line request."""
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            request_id = self.next_request_id()
            response = self.error_response(
                request_id=request_id,
                code="INVALID_JSON",
                message="Request must be valid JSON.",
            )
            self.log_request(
                request_id=request_id,
                tool_name="invalid_json",
                arguments={"raw_line_length": len(raw_line)},
                response=response,
            )
            return response
        return self.handle_payload(payload)

    def handle_payload(self, payload: object) -> dict[str, object]:
        """Validate and dispatch a parsed payload."""
        parsed = self.parse_request(payload)
        if isinstance(parsed, dict):
            request_id_value = parsed.get("request_id")
            request_id = (
                request_id_value if isinstance(request_id_value, str) else self.next_request_id()
            )
            self.log_request(
                request_id=request_id,
                tool_name="invalid_request",
                arguments={},
                response=parsed,
            )
            return parsed

        request = parsed
        tool_name: str
        arguments: dict[str, object]
        if request.method == "tools/call":
            tool_name_value = request.params.get("name")
            arguments_value = request.params.get("arguments", {})
            if not isinstance(tool_name_value, str) or not tool_name_value:
                return self.error_response(
                    request_id=request.request_id,
                    code="INVALID_PARAMS",
                    message="tools/call params.name must be a non-empty string.",
                )
            if not isinstance(arguments_value, dict):
                return self.error_response(
                    request_id=request.request_id,
                    code="INVALID_PARAMS",
                    message="tools/call params.arguments must be an object.",
                )
            tool_name = tool_name_value
            arguments = arguments_value
        else:
            tool_name = request.method
            arguments = request.params

        try:
            result = self._registry.dispatch(name=tool_name, arguments=arguments)
        except PathBlockedError as error:
            response = self.blocked_response(
                request_id=request.request_id,
                reason=error.reason,
                hint=error.hint,
            )
            self.log_request(
                request_id=request.request_id,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
            return response
        except PolicyBlockedError as error:
            response = self.blocked_response(
                request_id=request.request_id,
                reason=error.reason,
                hint=error.hint,
            )
            self.log_request(
                request_id=request.request_id,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
            return response
        except ToolDispatchError as error:
            response = self.error_response(
                request_id=request.request_id,
                code=error.code,
                message=error.message,
            )
            self.log_request(
                request_id=request.request_id,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
            return response
        except IndexSchemaUnsupportedError as error:
            response = self.error_response(
                request_id=request.request_id,
                code="INDEX_SCHEMA_UNSUPPORTED",
                message=(
                    f"Stored index schema {error.found} is unsupported; expected "
                    f"{error.expected}. Run repo.refresh_index with force=true."
                ),
            )
            self.log_request(
                request_id=request.request_id,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
            return response
        except Exception:
            response = self.error_response(
                request_id=request.request_id,
                code="INTERNAL_ERROR",
                message="Unhandled server error while executing tool.",
            )
            self.log_request(
                request_id=request.request_id,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
            return response

        warnings = _extract_result_warnings(result)
        response = self.success_response(
            request_id=request.request_id,
            result=result,
            warnings=warnings,
        )
        enforced = self.enforce_response_size_limit(
            request_id=request.request_id, response=response
        )
        self.log_request(
            request_id=request.request_id,
            tool_name=tool_name,
            arguments=arguments,
            response=enforced,
        )
        return enforced

    def parse_request(self, payload: object) -> Request | dict[str, object]:
        """Validate request payload and return normalized Request."""
        if not isinstance(payload, dict):
            return self.error_response(
                request_id=self.next_request_id(),
                code="INVALID_REQUEST",
                message="Request must be an object.",
            )

        request_id = self.extract_request_id(payload.get("id"))
        method = payload.get("method")
        params = payload.get("params", {})

        if not isinstance(method, str) or not method:
            return self.error_response(
                request_id=request_id,
                code="INVALID_REQUEST",
                message="Request method must be a non-empty string.",
            )
        if not isinstance(params, dict):
            return self.error_response(
                request_id=request_id,
                code="INVALID_PARAMS",
                message="Request params must be an object.",
            )

        return Request(request_id=request_id, method=method, params=params)

    def extract_request_id(self, request_id: object) -> str:
        """Extract request ID from payload or synthesize deterministic fallback."""
        if isinstance(request_id, str) and request_id:
            return request_id
        if isinstance(request_id, int):
            return str(request_id)
        return self.next_request_id()

    def next_request_id(self) -> str:
        """Generate deterministic fallback request IDs for invalid/missing IDs."""
        self._fallback_request_counter += 1
        return f"req-{self._fallback_request_counter:06d}"

    @staticmethod
    def success_response(
        request_id: str,
        result: dict[str, object],
        warnings: list[str] | None = None,
    ) -> dict[str, object]:
        """Build success envelope."""
        return {
            "request_id": request_id,
            "ok": True,
            "result": result,
            "warnings": warnings or [],
            "blocked": False,
        }

    @staticmethod
    def error_response(request_id: str, code: str, message: str) -> dict[str, object]:
        """Build explicit error envelope."""
        return {
            "request_id": request_id,
            "ok": False,
            "result": {},
            "warnings": [],
            "blocked": False,
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def blocked_response(request_id: str, reason: str, hint: str) -> dict[str, object]:
        """Build explicit blocked response envelope."""
        return {
            "request_id": request_id,
            "ok": False,
            "result": {"reason": reason, "hint": hint},
            "warnings": [],
            "blocked": True,
            "error": {"code": "PATH_BLOCKED", "message": reason},
        }

    def enforce_response_size_limit(
        self,
        request_id: str,
        response: dict[str, object],
    ) -> dict[str, object]:
        """Block responses that exceed max_total_bytes_per_response."""
        response_bytes = len(json.dumps(response, sort_keys=True).encode("utf-8"))
        if response_bytes <= self._limits.max_total_bytes_per_response:
            return response
        return self.blocked_response(
            request_id=request_id,
            reason="Response exceeds max_total_bytes_per_response limit.",
            hint="Request fewer lines or lower result volume.",
        )

    def log_request(
        self,
        request_id: str,
        tool_name: str,
        arguments: dict[str, object],
        response: dict[str, object],
    ) -> None:
        """Log one sanitized request event."""
        error_payload = response.get("error")
        error_code: str | None = None
        if isinstance(error_payload, dict):
            code_value = error_payload.get("code")
            if isinstance(code_value, str):
                error_code = code_value
        event = AuditEvent(
            timestamp=utc_timestamp(),
            request_id=request_id,
            tool=tool_name,
            ok=bool(response.get("ok", False)),
            blocked=bool(response.get("blocked", False)),
            error_code=error_code,
            metadata=sanitize_arguments(arguments),
        )
        self._audit_logger.append(event)

    def _outline_path(self, path: str) -> dict[str, object]:
        resolved = resolve_repo_path(repo_root=self._repo_root, candidate=path)
        enforce_file_access_policy(
            repo_root=self._repo_root,
            resolved_path=resolved,
            limits=self._limits,
        )
        if not resolved.exists() or not resolved.is_file():
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message=f"repo.outline path is not a readable file: {path}",
            )
        relative_path = resolved.relative_to(self._repo_root).as_posix()
        text = resolved.read_text(encoding="utf-8", errors="replace")
        adapter = self._adapters.select(relative_path)
        symbols = normalize_and_sort_symbols(adapter.outline(relative_path, text))
        return {
            "path": relative_path,
            "language": adapter.name,
            "symbols": [
                {
                    "kind": symbol.kind,
                    "name": symbol.name,
                    "signature": symbol.signature,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "doc": symbol.doc,
                    "parent_symbol": symbol.parent_symbol,
                    "scope_kind": symbol.scope_kind,
                    "is_conditional": symbol.is_conditional,
                    "decl_context": symbol.decl_context,
                }
                for symbol in symbols
            ],
        }

    def _list_files(self, arguments: dict[str, object]) -> dict[str, object]:
        glob_value = arguments.get("glob")
        include_hidden_value = arguments.get("include_hidden", False)
        max_results_value = arguments.get("max_results", self._limits.max_search_hits)

        file_glob = glob_value if isinstance(glob_value, str) else None
        include_hidden = include_hidden_value if isinstance(include_hidden_value, bool) else False
        max_results = (
            max_results_value
            if isinstance(max_results_value, int)
            else self._limits.max_search_hits
        )
        if max_results < 1:
            max_results = 1
        if max_results > self._limits.max_search_hits:
            max_results = self._limits.max_search_hits

        files: list[dict[str, object]] = []
        for candidate in sorted(self._repo_root.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.is_relative_to(self._data_dir):
                continue
            relative = candidate.relative_to(self._repo_root).as_posix()
            if not include_hidden and _is_hidden_path(relative):
                continue
            if file_glob is not None and not fnmatch.fnmatch(relative, file_glob):
                continue
            try:
                enforce_file_access_policy(
                    repo_root=self._repo_root,
                    resolved_path=candidate,
                    limits=self._limits,
                )
            except PolicyBlockedError:
                continue
            stat = candidate.stat()
            files.append(
                {
                    "path": relative,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime_ns,
                }
            )
            if len(files) >= max_results:
                break
        return {"files": files}

    def _read_repo_lines(self, path: str, start_line: int, end_line: int) -> list[str]:
        resolved = resolve_repo_path(repo_root=self._repo_root, candidate=path)
        enforce_file_access_policy(
            repo_root=self._repo_root,
            resolved_path=resolved,
            limits=self._limits,
        )
        if not resolved.exists() or not resolved.is_file():
            return []
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        start_index = max(0, start_line - 1)
        end_index = min(len(lines), end_line)
        return lines[start_index:end_index]

    def _build_context_bundle(self, arguments: dict[str, object]) -> dict[str, object]:
        budget_payload = arguments.get("budget", {})
        if not isinstance(budget_payload, dict):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle budget must be an object.",
            )

        max_files = budget_payload.get("max_files")
        max_total_lines = budget_payload.get("max_total_lines")
        if not isinstance(max_files, int) or not isinstance(max_total_lines, int):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle budget values must be integers.",
            )

        prompt = arguments.get("prompt")
        if not isinstance(prompt, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle prompt must be a string.",
            )

        include_tests = arguments.get("include_tests", True)
        if not isinstance(include_tests, bool):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle include_tests must be boolean.",
            )

        result = build_context_bundle(
            prompt=prompt,
            budget=BundleBudget(max_files=max_files, max_total_lines=max_total_lines),
            search_fn=self._index_manager.search,
            read_lines_fn=self._read_repo_lines,
            outline_fn=self._bundle_outline_symbols,
            reference_lookup_fn=self._bundle_reference_lookup(),
            include_tests=include_tests,
            strategy="hybrid",
            top_k_per_query=self._limits.max_search_hits,
            profile_sink=self._write_bundler_profile if self._bundler_profile_enabled else None,
        )
        response = _bundle_result_to_dict(result)
        warnings = self._write_last_bundle_artifacts(response)
        if warnings:
            response["__warnings__"] = warnings
        return response

    def _resolve_references(self, arguments: dict[str, object]) -> dict[str, object]:
        symbol_value = arguments.get("symbol")
        if not isinstance(symbol_value, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.references symbol must be a string.",
            )
        symbol = symbol_value.strip()
        if not symbol:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.references symbol must be a non-empty string.",
            )

        path_value = arguments.get("path")
        path_scope = path_value.strip() if isinstance(path_value, str) else None

        top_k_value = arguments.get("top_k", self._limits.max_references)
        if isinstance(top_k_value, int) and top_k_value > self._limits.max_references:
            raise PolicyBlockedError(
                reason="Requested top_k exceeds max_references limit.",
                hint="Reduce top_k or adjust the configured references limit.",
            )
        if not isinstance(top_k_value, int):
            top_k_value = self._limits.max_references
        if top_k_value < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.references top_k must be >= 1.",
            )

        profile_entry: dict[str, object] | None = (
            {
                "symbol_length": len(symbol),
                "path_scope_present": path_scope is not None,
                "top_k": top_k_value,
            }
            if self._reference_profile_enabled
            else None
        )
        started = time.perf_counter()
        files = self._reference_source_files(path_scope, profile_entry)
        candidates = self._collect_symbol_references(
            symbol=symbol, files=files, profile=profile_entry
        )
        resolve_elapsed = time.perf_counter() - started
        total_candidates = len(candidates)
        limited = candidates[:top_k_value]
        if profile_entry is not None:
            profile_entry["resolve_references_seconds"] = resolve_elapsed
            profile_entry["total_candidates"] = total_candidates
            profile_entry["returned_candidates"] = len(limited)
            profile_entry["truncated"] = len(limited) < total_candidates
            self._write_references_profile(profile_entry)
        return {
            "symbol": symbol,
            "references": [asdict(item) for item in limited],
            "truncated": len(limited) < total_candidates,
            "total_candidates": total_candidates,
        }

    def _reference_source_files(
        self,
        path_scope: str | None,
        profile: dict[str, object] | None = None,
    ) -> list[tuple[str, str]]:
        started = time.perf_counter()
        if path_scope is not None:
            policy_started = time.perf_counter()
            resolved = resolve_repo_path(repo_root=self._repo_root, candidate=path_scope)
            enforce_file_access_policy(
                repo_root=self._repo_root,
                resolved_path=resolved,
                limits=self._limits,
            )
            policy_elapsed = time.perf_counter() - policy_started
            if not resolved.exists() or not resolved.is_file():
                raise ToolDispatchError(
                    code="INVALID_PARAMS",
                    message=f"repo.references path is not a readable file: {path_scope}",
                )
            relative = resolved.relative_to(self._repo_root).as_posix()
            read_started = time.perf_counter()
            text = resolved.read_text(encoding="utf-8", errors="replace")
            read_elapsed = time.perf_counter() - read_started
            if profile is not None:
                profile["candidate_discovery"] = {
                    "mode": "path",
                    "records_discovered": 1,
                    "records_allowed": 1,
                    "records_blocked": 0,
                    "discover_files_seconds": 0.0,
                    "policy_seconds": policy_elapsed,
                    "read_files_seconds": read_elapsed,
                    "candidate_discovery_seconds": time.perf_counter() - started,
                }
            return [(relative, text)]

        files: list[tuple[str, str]] = []
        discover_started = time.perf_counter()
        records = discover_files(self._repo_root, self._config.index)
        discover_elapsed = time.perf_counter() - discover_started
        policy_seconds = 0.0
        read_seconds = 0.0
        blocked = 0
        for record in records:
            candidate = self._repo_root / record.path
            policy_started = time.perf_counter()
            try:
                enforce_file_access_policy(
                    repo_root=self._repo_root,
                    resolved_path=candidate,
                    limits=self._limits,
                )
            except PolicyBlockedError:
                policy_seconds += time.perf_counter() - policy_started
                blocked += 1
                continue
            policy_seconds += time.perf_counter() - policy_started
            read_started = time.perf_counter()
            text = candidate.read_text(encoding="utf-8", errors="replace")
            read_seconds += time.perf_counter() - read_started
            files.append((record.path, text))
        if profile is not None:
            profile["candidate_discovery"] = {
                "mode": "discover",
                "records_discovered": len(records),
                "records_allowed": len(files),
                "records_blocked": blocked,
                "discover_files_seconds": discover_elapsed,
                "policy_seconds": policy_seconds,
                "read_files_seconds": read_seconds,
                "candidate_discovery_seconds": time.perf_counter() - started,
            }
        return files

    def _collect_symbol_references(
        self,
        symbol: str,
        files: list[tuple[str, str]],
        profile: dict[str, object] | None = None,
    ) -> list[SymbolReference]:
        by_path: dict[str, list[tuple[str, str]]] = {}
        for path, text in files:
            by_path.setdefault(path, []).append((path, text))

        references: list[SymbolReference] = []
        select_seconds = 0.0
        resolver_seconds = 0.0
        resolver_failures = 0
        adapter_stats: dict[str, dict[str, object]] = {}
        for path in sorted(by_path.keys()):
            select_started = time.perf_counter()
            adapter = self._adapters.select(path)
            select_elapsed = time.perf_counter() - select_started
            select_seconds += select_elapsed
            resolver = getattr(adapter, "references_for_symbol", None)
            adapter_bucket = adapter_stats.setdefault(
                adapter.name,
                {
                    "paths": 0,
                    "select_seconds": 0.0,
                    "resolver_calls": 0,
                    "resolver_seconds": 0.0,
                    "resolver_failures": 0,
                },
            )
            adapter_bucket["paths"] = int(adapter_bucket["paths"]) + 1
            adapter_bucket["select_seconds"] = (
                float(adapter_bucket["select_seconds"]) + select_elapsed
            )
            if not callable(resolver):
                continue
            resolver_started = time.perf_counter()
            try:
                resolved = resolver(symbol, by_path[path], top_k=None)
            except Exception:
                resolver_elapsed = time.perf_counter() - resolver_started
                resolver_seconds += resolver_elapsed
                resolver_failures += 1
                adapter_bucket["resolver_calls"] = int(adapter_bucket["resolver_calls"]) + 1
                adapter_bucket["resolver_seconds"] = (
                    float(adapter_bucket["resolver_seconds"]) + resolver_elapsed
                )
                adapter_bucket["resolver_failures"] = int(adapter_bucket["resolver_failures"]) + 1
                continue
            resolver_elapsed = time.perf_counter() - resolver_started
            resolver_seconds += resolver_elapsed
            adapter_bucket["resolver_calls"] = int(adapter_bucket["resolver_calls"]) + 1
            adapter_bucket["resolver_seconds"] = (
                float(adapter_bucket["resolver_seconds"]) + resolver_elapsed
            )
            references.extend(resolved)
        normalize_started = time.perf_counter()
        normalized = normalize_and_sort_references(references)
        normalize_elapsed = time.perf_counter() - normalize_started
        if profile is not None:
            profile["adapter_resolution"] = {
                "unique_paths": len(by_path),
                "adapter_select_seconds": select_seconds,
                "resolver_seconds": resolver_seconds,
                "resolver_failures": resolver_failures,
                "normalize_sort_seconds": normalize_elapsed,
                "adapters": {
                    name: {
                        "paths": int(values["paths"]),
                        "select_seconds": float(values["select_seconds"]),
                        "resolver_calls": int(values["resolver_calls"]),
                        "resolver_seconds": float(values["resolver_seconds"]),
                        "resolver_failures": int(values["resolver_failures"]),
                    }
                    for name, values in sorted(adapter_stats.items())
                },
            }
        return normalized

    def _write_references_profile(self, payload: dict[str, object]) -> None:
        if not self._reference_profile_enabled:
            return
        self._reference_profile_sequence += 1
        entry = {
            "timestamp": utc_timestamp(),
            "sequence": self._reference_profile_sequence,
            **payload,
        }
        try:
            self._reference_profile_path.parent.mkdir(parents=True, exist_ok=True)
            with self._reference_profile_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True))
                handle.write("\n")
        except OSError:
            return

    def _write_bundler_profile(self, payload: dict[str, object]) -> None:
        if not self._bundler_profile_enabled:
            return
        self._bundler_profile_sequence += 1
        entry = {
            "timestamp": utc_timestamp(),
            "sequence": self._bundler_profile_sequence,
            **payload,
        }
        try:
            self._bundler_profile_path.parent.mkdir(parents=True, exist_ok=True)
            with self._bundler_profile_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True))
                handle.write("\n")
        except OSError:
            return

    def _write_last_bundle_artifacts(self, payload: dict[str, object]) -> list[str]:
        warnings: list[str] = []
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warnings.append(f"Failed to prepare data_dir for bundle artifacts: {error}")
            return warnings
        json_path = self._data_dir / "last_bundle.json"
        md_path = self._data_dir / "last_bundle.md"
        try:
            with json_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, indent=2)
                handle.write("\n")
        except OSError as error:
            warnings.append(f"Failed to write last_bundle.json: {error}")
        try:
            markdown = _bundle_markdown(payload)
            with md_path.open("w", encoding="utf-8") as handle:
                handle.write(markdown)
        except OSError as error:
            warnings.append(f"Failed to write last_bundle.md: {error}")
        return warnings

    def _bundle_outline_symbols(self, path: str) -> list[dict[str, object]]:
        """Return outline symbols for bundling, falling back safely on errors."""
        try:
            outlined = self._outline_path(path)
        except Exception:
            return []
        symbols = outlined.get("symbols", [])
        if not isinstance(symbols, list):
            return []
        safe_symbols: list[dict[str, object]] = []
        for item in symbols:
            if isinstance(item, dict):
                safe_symbols.append(item)
        return safe_symbols

    def _bundle_reference_lookup(self) -> Callable[[str], list[dict[str, object]]]:
        """Build lazy deterministic reference lookup closure for bundle ranking."""
        files_cache: list[tuple[str, str]] | None = None
        symbol_cache: dict[str, list[dict[str, object]]] = {}

        def lookup(symbol: str) -> list[dict[str, object]]:
            nonlocal files_cache
            cached = symbol_cache.get(symbol)
            if cached is not None:
                return cached
            if files_cache is None:
                files_cache = self._reference_source_files(None)
            references = self._collect_symbol_references(symbol=symbol, files=files_cache)
            payload = [asdict(item) for item in references]
            symbol_cache[symbol] = payload
            return payload

        return lookup


def create_server(
    repo_root: str,
    limits: object | None = None,
    data_dir: str | None = None,
    cli_overrides: CliOverrides | None = None,
) -> StdioServer:
    """Create a configured STDIO server instance."""
    legacy_max_file_bytes: int | None = None
    legacy_max_open_lines: int | None = None
    legacy_max_total_bytes: int | None = None
    legacy_max_search_hits: int | None = None
    legacy_max_references: int | None = None
    if limits is not None:
        legacy_max_file_bytes = getattr(limits, "max_file_bytes", None)
        legacy_max_open_lines = getattr(limits, "max_open_lines", None)
        legacy_max_total_bytes = getattr(limits, "max_total_bytes_per_response", None)
        legacy_max_search_hits = getattr(limits, "max_search_hits", None)
        legacy_max_references = getattr(limits, "max_references", None)

    overrides = CliOverrides(
        data_dir=Path(data_dir).resolve() if data_dir is not None else None,
        max_file_bytes=legacy_max_file_bytes,
        max_open_lines=legacy_max_open_lines,
        max_total_bytes_per_response=legacy_max_total_bytes,
        max_search_hits=legacy_max_search_hits,
        max_references=legacy_max_references,
    )
    if cli_overrides is not None:
        overrides = CliOverrides(
            data_dir=cli_overrides.data_dir or overrides.data_dir,
            max_file_bytes=(
                cli_overrides.max_file_bytes
                if cli_overrides.max_file_bytes is not None
                else overrides.max_file_bytes
            ),
            max_open_lines=(
                cli_overrides.max_open_lines
                if cli_overrides.max_open_lines is not None
                else overrides.max_open_lines
            ),
            max_total_bytes_per_response=(
                cli_overrides.max_total_bytes_per_response
                if cli_overrides.max_total_bytes_per_response is not None
                else overrides.max_total_bytes_per_response
            ),
            max_search_hits=(
                cli_overrides.max_search_hits
                if cli_overrides.max_search_hits is not None
                else overrides.max_search_hits
            ),
            max_references=(
                cli_overrides.max_references
                if cli_overrides.max_references is not None
                else overrides.max_references
            ),
            python_enabled=cli_overrides.python_enabled,
        )

    config = load_effective_config(repo_root=Path(repo_root).resolve(), overrides=overrides)
    return StdioServer(config=config)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the repo interrogator server process."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    python_enabled: bool | None = None
    if args.python_adapter_enabled == "true":
        python_enabled = True
    if args.python_adapter_enabled == "false":
        python_enabled = False
    overrides = CliOverrides(
        data_dir=Path(args.data_dir).resolve() if args.data_dir is not None else None,
        max_file_bytes=args.max_file_bytes,
        max_open_lines=args.max_open_lines,
        max_total_bytes_per_response=args.max_total_bytes_per_response,
        max_search_hits=args.max_search_hits,
        max_references=args.max_references,
        python_enabled=python_enabled,
    )
    server = create_server(repo_root=args.repo_root, cli_overrides=overrides)
    server.serve(in_stream=sys.stdin, out_stream=sys.stdout)
    return 0


def _extract_result_warnings(result: dict[str, object]) -> list[str]:
    raw = result.pop("__warnings__", None)
    if not isinstance(raw, list):
        return []
    warnings: list[str] = []
    for item in raw:
        if isinstance(item, str):
            warnings.append(item)
    return warnings


def _bundle_result_to_dict(result: BundleResult) -> dict[str, object]:
    return {
        "bundle_id": result.bundle_id,
        "prompt_fingerprint": result.prompt_fingerprint,
        "strategy": result.strategy,
        "budget": asdict(result.budget),
        "totals": asdict(result.totals),
        "selections": [asdict(selection) for selection in result.selections],
        "citations": [asdict(citation) for citation in result.citations],
        "audit": {
            "search_queries": list(result.audit.search_queries),
            "dedupe_counts": {
                "before": result.audit.dedupe_before,
                "after": result.audit.dedupe_after,
            },
            "budget_enforcement": list(result.audit.budget_enforcement),
            "ranking_debug": {
                "candidate_count": result.audit.ranking_candidate_count,
                "definition_match_count": result.audit.ranking_definition_match_count,
                "reference_proximity_count": result.audit.ranking_reference_proximity_count,
                "top_candidates": [asdict(item) for item in result.audit.ranking_top_candidates],
            },
        },
    }


def _bundle_markdown(payload: dict[str, object]) -> str:
    lines = ["# Last Context Bundle", ""]
    bundle_id = payload.get("bundle_id")
    prompt_fingerprint = payload.get("prompt_fingerprint")
    strategy = payload.get("strategy")
    lines.append(f"- bundle_id: `{bundle_id}`")
    lines.append(f"- prompt_fingerprint: `{prompt_fingerprint}`")
    lines.append(f"- strategy: `{strategy}`")
    lines.append("")
    totals = payload.get("totals")
    if isinstance(totals, dict):
        lines.append("## Totals")
        lines.append(f"- selected_files: `{totals.get('selected_files')}`")
        lines.append(f"- selected_lines: `{totals.get('selected_lines')}`")
        lines.append(f"- truncated: `{totals.get('truncated')}`")
        lines.append("")
    selections = payload.get("selections")
    if isinstance(selections, list):
        lines.append("## Selections")
        for index, selection in enumerate(selections):
            if not isinstance(selection, dict):
                continue
            lines.append(f"### Selection {index + 1}")
            lines.append(f"- path: `{selection.get('path')}`")
            lines.append(f"- range: `{selection.get('start_line')}`-`{selection.get('end_line')}`")
            lines.append(f"- score: `{selection.get('score')}`")
            lines.append(f"- why_selected: `{selection.get('why_selected')}`")
            lines.append(f"- rationale: {selection.get('rationale')}")
            excerpt = selection.get("excerpt")
            if isinstance(excerpt, str):
                lines.append("")
                lines.append("```text")
                lines.append(excerpt)
                lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _is_hidden_path(relative: str) -> bool:
    for part in Path(relative).parts:
        if part.startswith("."):
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
