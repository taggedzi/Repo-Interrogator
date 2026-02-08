"""Built-in v1 tool stubs required by SPEC.md."""

from __future__ import annotations

from pathlib import Path

from repo_mcp.tools.registry import ToolHandler, ToolRegistry


def register_builtin_tools(registry: ToolRegistry, repo_root: Path) -> None:
    """Register the minimum v1 tool set with deterministic stub behavior."""
    registry.register("repo.status", _status_handler(repo_root))
    registry.register("repo.list_files", _list_files_handler)
    registry.register("repo.open_file", _open_file_handler)
    registry.register("repo.search", _search_handler)
    registry.register("repo.refresh_index", _refresh_index_handler)
    registry.register("repo.audit_log", _audit_log_handler)


def _status_handler(repo_root: Path) -> ToolHandler:
    def handler(_: dict[str, object]) -> dict[str, object]:
        return {
            "repo_root": str(repo_root),
            "index_status": "not_indexed",
            "last_refresh_timestamp": None,
            "indexed_file_count": 0,
            "enabled_adapters": [],
            "limits_summary": {},
        }

    return handler


def _list_files_handler(_: dict[str, object]) -> dict[str, object]:
    return {"files": []}


def _open_file_handler(arguments: dict[str, object]) -> dict[str, object]:
    path = arguments.get("path")
    path_value = path if isinstance(path, str) else ""
    return {"path": path_value, "numbered_lines": [], "truncated": False}


def _search_handler(_: dict[str, object]) -> dict[str, object]:
    return {"hits": []}


def _refresh_index_handler(_: dict[str, object]) -> dict[str, object]:
    return {"added": 0, "updated": 0, "removed": 0, "duration_ms": 0, "timestamp": None}


def _audit_log_handler(_: dict[str, object]) -> dict[str, object]:
    return {"entries": []}
