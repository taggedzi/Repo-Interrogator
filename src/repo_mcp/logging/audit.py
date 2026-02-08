"""Structured JSONL audit log utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AuditEvent:
    """Sanitized representation of a single tool request."""

    timestamp: str
    request_id: str
    tool: str
    ok: bool
    blocked: bool
    error_code: str | None
    metadata: dict[str, object]


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sanitize_arguments(arguments: dict[str, object]) -> dict[str, object]:
    """Sanitize arguments to avoid logging secret-like values."""
    sanitized: dict[str, object] = {}
    for key in sorted(arguments.keys()):
        value = arguments[key]
        if key in {"path", "glob", "file_glob", "mode"} and isinstance(value, str):
            sanitized[key] = value
            continue
        if key in {"start_line", "end_line", "top_k", "max_results", "limit"} and isinstance(
            value, int
        ):
            sanitized[key] = value
            continue
        if key in {"include_hidden", "force", "include_tests"} and isinstance(value, bool):
            sanitized[key] = value
            continue
        if key in {"query", "prompt"} and isinstance(value, str):
            sanitized[f"{key}_present"] = True
            sanitized[f"{key}_length"] = len(value)
            continue
        if isinstance(value, (int, float, bool)) or value is None:
            sanitized[key] = value
            continue
        if isinstance(value, str):
            sanitized[f"{key}_present"] = True
            sanitized[f"{key}_length"] = len(value)
            continue
        if isinstance(value, list):
            sanitized[f"{key}_type"] = "list"
            sanitized[f"{key}_length"] = len(value)
            continue
        if isinstance(value, dict):
            sanitized[f"{key}_type"] = "dict"
            sanitized[f"{key}_keys"] = sorted(str(k) for k in value.keys())
            continue
        sanitized[f"{key}_type"] = type(value).__name__
    return sanitized


class JsonlAuditLogger:
    """Append-only JSONL audit logger and bounded reader."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Return on-disk JSONL path."""
        return self._path

    def append(self, event: AuditEvent) -> None:
        """Append a sanitized event as one JSON object per line."""
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True))
            handle.write("\n")

    def read(self, since: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        """Read recent events, optionally filtered by timestamp lower bound."""
        if limit < 1:
            return []
        entries: list[dict[str, object]] = []
        if not self._path.exists():
            return entries
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if since is not None:
                    ts = record.get("timestamp")
                    if not isinstance(ts, str) or ts < since:
                        continue
                entries.append(record)
        if len(entries) <= limit:
            return entries
        return entries[-limit:]
