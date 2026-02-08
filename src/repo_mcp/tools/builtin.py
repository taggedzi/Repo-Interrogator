"""Built-in v1 tool stubs required by SPEC.md."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from repo_mcp.config import ServerConfig
from repo_mcp.index import (
    DEFAULT_CHUNK_LINES,
    DEFAULT_CHUNK_OVERLAP_LINES,
    IndexStatus,
)
from repo_mcp.security import (
    PolicyBlockedError,
    SecurityLimits,
    enforce_file_access_policy,
    enforce_open_line_limits,
    resolve_repo_path,
)
from repo_mcp.tools.registry import ToolHandler, ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
    repo_root: Path,
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
    refresh_index: Callable[[bool], dict[str, object]],
    read_index_status: Callable[[], IndexStatus],
    config: ServerConfig,
) -> None:
    """Register the minimum v1 tool set with deterministic stub behavior."""
    registry.register(
        "repo.status",
        _status_handler(repo_root, limits, config, read_index_status),
    )
    registry.register("repo.list_files", _list_files_handler)
    registry.register("repo.open_file", _open_file_handler(repo_root, limits))
    registry.register("repo.search", _search_handler(limits))
    registry.register("repo.refresh_index", _refresh_index_handler(refresh_index))
    registry.register("repo.audit_log", _audit_log_handler(limits, read_audit_entries))


def _status_handler(
    repo_root: Path,
    limits: SecurityLimits,
    config: ServerConfig,
    read_index_status: Callable[[], IndexStatus],
) -> ToolHandler:
    def handler(_: dict[str, object]) -> dict[str, object]:
        index_status = read_index_status()
        enabled_adapters: list[str] = []
        if config.adapters.python_enabled:
            enabled_adapters.append("python")
        return {
            "repo_root": str(repo_root),
            "index_status": index_status.index_status,
            "last_refresh_timestamp": index_status.last_refresh_timestamp,
            "indexed_file_count": index_status.indexed_file_count,
            "enabled_adapters": enabled_adapters,
            "limits_summary": {
                "max_file_bytes": limits.max_file_bytes,
                "max_open_lines": limits.max_open_lines,
                "max_total_bytes_per_response": limits.max_total_bytes_per_response,
                "max_search_hits": limits.max_search_hits,
            },
            "chunking_summary": {
                "chunk_lines": DEFAULT_CHUNK_LINES,
                "overlap_lines": DEFAULT_CHUNK_OVERLAP_LINES,
                "indexed_chunk_count": index_status.indexed_chunk_count,
            },
            "effective_config": config.to_public_dict(),
        }

    return handler


def _list_files_handler(_: dict[str, object]) -> dict[str, object]:
    return {"files": []}


def _open_file_handler(repo_root: Path, limits: SecurityLimits) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        path_value = arguments.get("path")
        if not isinstance(path_value, str) or not path_value:
            return {"path": "", "numbered_lines": [], "truncated": False}

        resolved = resolve_repo_path(repo_root=repo_root, candidate=path_value)
        enforce_file_access_policy(repo_root=repo_root, resolved_path=resolved, limits=limits)
        if not resolved.exists() or not resolved.is_file():
            return {"path": path_value, "numbered_lines": [], "truncated": False}

        start_line_value = arguments.get("start_line", 1)
        end_line_value = arguments.get("end_line")

        start_line = start_line_value if isinstance(start_line_value, int) else 1
        end_line: int | None = end_line_value if isinstance(end_line_value, int) else None
        if start_line < 1:
            start_line = 1
        enforce_open_line_limits(start_line=start_line, end_line=end_line, limits=limits)

        content_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        if end_line is None and len(content_lines) > limits.max_open_lines:
            raise PolicyBlockedError(
                reason="Requested file exceeds max_open_lines limit without end_line.",
                hint="Specify end_line within allowed range.",
            )
        first_index = start_line - 1
        last_index = len(content_lines) if end_line is None else max(first_index, end_line)
        slice_lines = content_lines[first_index:last_index]
        numbered_lines = [
            {"line": first_index + idx + 1, "text": text} for idx, text in enumerate(slice_lines)
        ]
        return {"path": path_value, "numbered_lines": numbered_lines, "truncated": False}

    return handler


def _search_handler(limits: SecurityLimits) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        top_k_value = arguments.get("top_k", limits.max_search_hits)
        if isinstance(top_k_value, int) and top_k_value > limits.max_search_hits:
            raise PolicyBlockedError(
                reason="Requested top_k exceeds max_search_hits limit.",
                hint="Reduce top_k or adjust the configured search limit.",
            )
        return {"hits": []}

    return handler


def _refresh_index_handler(refresh_index: Callable[[bool], dict[str, object]]) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        force_value = arguments.get("force", False)
        force = force_value if isinstance(force_value, bool) else False
        return refresh_index(force)

    return handler


def _audit_log_handler(
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        since_value = arguments.get("since")
        limit_value = arguments.get("limit", limits.max_search_hits)

        since: str | None = since_value if isinstance(since_value, str) else None
        limit = limit_value if isinstance(limit_value, int) else limits.max_search_hits
        if limit < 1:
            limit = 1
        if limit > limits.max_search_hits:
            limit = limits.max_search_hits

        return {"entries": read_audit_entries(since, limit)}

    return handler
