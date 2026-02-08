"""Deterministic tool registration primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

ToolHandler = Callable[[dict[str, object]], dict[str, object]]


@dataclass(slots=True, frozen=True)
class ToolDispatchError(Exception):
    """Represents deterministic tool dispatch failures."""

    code: str
    message: str


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

    def names(self) -> tuple[str, ...]:
        """Return registered tool names in deterministic order."""
        return tuple(self._handlers.keys())

    def dispatch(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Dispatch to a registered tool by name."""
        handler = self.get(name)
        if handler is None:
            raise ToolDispatchError(code="UNKNOWN_TOOL", message=f"Unknown tool: {name}")
        return handler(arguments)
