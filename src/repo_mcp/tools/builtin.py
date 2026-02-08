"""Built-in v1 tool stubs required by SPEC.md."""

from __future__ import annotations

from pathlib import Path

from repo_mcp.security import resolve_repo_path
from repo_mcp.tools.registry import ToolHandler, ToolRegistry


def register_builtin_tools(registry: ToolRegistry, repo_root: Path) -> None:
    """Register the minimum v1 tool set with deterministic stub behavior."""
    registry.register("repo.status", _status_handler(repo_root))
    registry.register("repo.list_files", _list_files_handler)
    registry.register("repo.open_file", _open_file_handler(repo_root))
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


def _open_file_handler(repo_root: Path) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        path_value = arguments.get("path")
        if not isinstance(path_value, str) or not path_value:
            return {"path": "", "numbered_lines": [], "truncated": False}

        resolved = resolve_repo_path(repo_root=repo_root, candidate=path_value)
        if not resolved.exists() or not resolved.is_file():
            return {"path": path_value, "numbered_lines": [], "truncated": False}

        start_line_value = arguments.get("start_line", 1)
        end_line_value = arguments.get("end_line")

        start_line = start_line_value if isinstance(start_line_value, int) else 1
        end_line: int | None = end_line_value if isinstance(end_line_value, int) else None
        if start_line < 1:
            start_line = 1

        content_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        first_index = start_line - 1
        last_index = len(content_lines) if end_line is None else max(first_index, end_line)
        slice_lines = content_lines[first_index:last_index]
        numbered_lines = [
            {"line": first_index + idx + 1, "text": text} for idx, text in enumerate(slice_lines)
        ]
        return {"path": path_value, "numbered_lines": numbered_lines, "truncated": False}

    return handler


def _search_handler(_: dict[str, object]) -> dict[str, object]:
    return {"hits": []}


def _refresh_index_handler(_: dict[str, object]) -> dict[str, object]:
    return {"added": 0, "updated": 0, "removed": 0, "duration_ms": 0, "timestamp": None}


def _audit_log_handler(_: dict[str, object]) -> dict[str, object]:
    return {"entries": []}
