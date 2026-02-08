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
from repo_mcp.tools.registry import ToolDispatchError, ToolHandler, ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
    repo_root: Path,
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
    list_files: Callable[[dict[str, object]], dict[str, object]],
    refresh_index: Callable[[bool], dict[str, object]],
    read_index_status: Callable[[], IndexStatus],
    search_index: Callable[[str, int, str | None, str | None], list[dict[str, object]]],
    outline_path: Callable[[str], dict[str, object]],
    build_context_bundle: Callable[[dict[str, object]], dict[str, object]],
    config: ServerConfig,
) -> None:
    """Register the minimum v1 tool set with deterministic stub behavior."""
    registry.register(
        "repo.status",
        _status_handler(repo_root, limits, config, read_index_status),
    )
    registry.register("repo.list_files", _list_files_handler(list_files))
    registry.register("repo.open_file", _open_file_handler(repo_root, limits))
    registry.register("repo.outline", _outline_handler(outline_path))
    registry.register("repo.search", _search_handler(limits, search_index))
    registry.register(
        "repo.build_context_bundle",
        _build_context_bundle_handler(build_context_bundle),
    )
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


def _list_files_handler(
    list_files: Callable[[dict[str, object]], dict[str, object]],
) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        return list_files(arguments)

    return handler


def _outline_handler(outline_path: Callable[[str], dict[str, object]]) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        path_value = arguments.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.outline path must be a non-empty string.",
            )
        return outline_path(path_value)

    return handler


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


def _search_handler(
    limits: SecurityLimits,
    search_index: Callable[[str, int, str | None, str | None], list[dict[str, object]]],
) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        mode_value = arguments.get("mode", "bm25")
        if not isinstance(mode_value, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS", message="repo.search mode must be a string."
            )
        if mode_value != "bm25":
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.search mode must be 'bm25' in v1.",
            )
        query_value = arguments.get("query")
        if not isinstance(query_value, str) or not query_value.strip():
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.search query must be a non-empty string.",
            )

        top_k_value = arguments.get("top_k", limits.max_search_hits)
        if isinstance(top_k_value, int) and top_k_value > limits.max_search_hits:
            raise PolicyBlockedError(
                reason="Requested top_k exceeds max_search_hits limit.",
                hint="Reduce top_k or adjust the configured search limit.",
            )
        if not isinstance(top_k_value, int):
            top_k_value = limits.max_search_hits
        if top_k_value < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.search top_k must be >= 1.",
            )

        file_glob_value = arguments.get("file_glob")
        file_glob = file_glob_value if isinstance(file_glob_value, str) else None
        path_prefix_value = arguments.get("path_prefix")
        path_prefix = path_prefix_value if isinstance(path_prefix_value, str) else None
        hits = search_index(
            query_value,
            top_k_value,
            file_glob,
            path_prefix,
        )
        return {"hits": hits}

    return handler


def _build_context_bundle_handler(
    build_context_bundle: Callable[[dict[str, object]], dict[str, object]],
) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        prompt = arguments.get("prompt")
        budget = arguments.get("budget")
        strategy = arguments.get("strategy", "hybrid")
        include_tests = arguments.get("include_tests", True)

        if not isinstance(prompt, str) or not prompt.strip():
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle prompt must be a non-empty string.",
            )
        if not isinstance(budget, dict):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle budget must be an object.",
            )
        if not isinstance(strategy, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle strategy must be a string.",
            )
        if strategy != "hybrid":
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle strategy must be 'hybrid' in v1.",
            )
        if not isinstance(include_tests, bool):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle include_tests must be a boolean.",
            )

        max_files = budget.get("max_files")
        max_total_lines = budget.get("max_total_lines")
        if not isinstance(max_files, int) or max_files < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle budget.max_files must be >= 1.",
            )
        if not isinstance(max_total_lines, int) or max_total_lines < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle budget.max_total_lines must be >= 1.",
            )

        return build_context_bundle(
            {
                "prompt": prompt,
                "budget": {
                    "max_files": max_files,
                    "max_total_lines": max_total_lines,
                },
                "strategy": strategy,
                "include_tests": include_tests,
            }
        )

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
