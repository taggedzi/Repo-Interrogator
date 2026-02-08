"""STDIO MCP server entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from repo_mcp.config import CliOverrides, ServerConfig, load_effective_config
from repo_mcp.index import IndexManager, IndexSchemaUnsupportedError
from repo_mcp.logging import AuditEvent, JsonlAuditLogger, sanitize_arguments, utc_timestamp
from repo_mcp.security import PathBlockedError, PolicyBlockedError
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
            refresh_index=self._index_manager.refresh,
            read_index_status=self._index_manager.status,
            config=self._config,
        )
        self._fallback_request_counter = 0

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

        response = self.success_response(request_id=request.request_id, result=result)
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
    def success_response(request_id: str, result: dict[str, object]) -> dict[str, object]:
        """Build success envelope."""
        return {
            "request_id": request_id,
            "ok": True,
            "result": result,
            "warnings": [],
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
    if limits is not None:
        legacy_max_file_bytes = getattr(limits, "max_file_bytes", None)
        legacy_max_open_lines = getattr(limits, "max_open_lines", None)
        legacy_max_total_bytes = getattr(limits, "max_total_bytes_per_response", None)
        legacy_max_search_hits = getattr(limits, "max_search_hits", None)

    overrides = CliOverrides(
        data_dir=Path(data_dir).resolve() if data_dir is not None else None,
        max_file_bytes=legacy_max_file_bytes,
        max_open_lines=legacy_max_open_lines,
        max_total_bytes_per_response=legacy_max_total_bytes,
        max_search_hits=legacy_max_search_hits,
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
        python_enabled=python_enabled,
    )
    server = create_server(repo_root=args.repo_root, cli_overrides=overrides)
    server.serve(in_stream=sys.stdin, out_stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
