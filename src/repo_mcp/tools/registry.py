"""Deterministic tool registration primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

ToolHandler = Callable[[dict[str, object]], dict[str, object]]


@dataclass(slots=True)
class ToolRegistry:
    """In-memory tool registry preserving deterministic insertion order."""

    _handlers: dict[str, ToolHandler] = field(default_factory=dict)

    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a named handler."""
        self._handlers[name] = handler

    def get(self, name: str) -> ToolHandler | None:
        """Return a handler by name."""
        return self._handlers.get(name)
