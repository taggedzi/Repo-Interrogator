"""Audit event data types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AuditEvent:
    """Sanitized representation of a single tool request."""

    request_id: str
    tool: str
    blocked: bool
