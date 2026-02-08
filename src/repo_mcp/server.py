"""STDIO MCP server entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from repo_mcp.security import PathBlockedError, PolicyBlockedError, SecurityLimits
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
    return parser


class StdioServer:
    """Minimal deterministic STDIO server for tool routing."""

    def __init__(self, repo_root: Path, limits: SecurityLimits | None = None) -> None:
        self._repo_root = repo_root
        self._limits = limits or SecurityLimits()
        self._registry = ToolRegistry()
        register_builtin_tools(self._registry, repo_root=repo_root, limits=self._limits)
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
            return self.error_response(
                request_id=self.next_request_id(),
                code="INVALID_JSON",
                message="Request must be valid JSON.",
            )
        return self.handle_payload(payload)

    def handle_payload(self, payload: object) -> dict[str, object]:
        """Validate and dispatch a parsed payload."""
        parsed = self.parse_request(payload)
        if isinstance(parsed, dict):
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
            return self.blocked_response(
                request_id=request.request_id,
                reason=error.reason,
                hint=error.hint,
            )
        except PolicyBlockedError as error:
            return self.blocked_response(
                request_id=request.request_id,
                reason=error.reason,
                hint=error.hint,
            )
        except ToolDispatchError as error:
            return self.error_response(
                request_id=request.request_id,
                code=error.code,
                message=error.message,
            )
        except Exception:
            return self.error_response(
                request_id=request.request_id,
                code="INTERNAL_ERROR",
                message="Unhandled server error while executing tool.",
            )

        response = self.success_response(request_id=request.request_id, result=result)
        return self.enforce_response_size_limit(request_id=request.request_id, response=response)

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


def create_server(repo_root: str, limits: SecurityLimits | None = None) -> StdioServer:
    """Create a configured STDIO server instance."""
    return StdioServer(repo_root=Path(repo_root).resolve(), limits=limits)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the repo interrogator server process."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    server = create_server(repo_root=args.repo_root)
    server.serve(in_stream=sys.stdin, out_stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
