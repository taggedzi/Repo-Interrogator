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


@dataclass(slots=True, frozen=True)
class ToolMetadata:
    """MCP tool definition metadata: name, description, and JSON Schema."""

    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(slots=True)
class ToolRegistry:
    """In-memory tool registry preserving deterministic insertion order."""

    _handlers: dict[str, ToolHandler] = field(default_factory=dict)
    _metadata: dict[str, ToolMetadata] = field(default_factory=dict)

    def register(
        self,
        name: str,
        handler: ToolHandler,
        metadata: ToolMetadata | None = None,
    ) -> None:
        """Register a named handler with optional MCP metadata."""
        self._handlers[name] = handler
        if metadata is not None:
            self._metadata[name] = metadata

    def get(self, name: str) -> ToolHandler | None:
        """Return a handler by name."""
        return self._handlers.get(name)

    def names(self) -> tuple[str, ...]:
        """Return registered tool names in deterministic order."""
        return tuple(self._handlers.keys())

    def list_tools(self) -> list[dict[str, object]]:
        """Return MCP tool definitions for all tools that have metadata registered."""
        result: list[dict[str, object]] = []
        for name in self._handlers:
            meta = self._metadata.get(name)
            if meta is not None:
                result.append(
                    {
                        "description": meta.description,
                        "inputSchema": meta.input_schema,
                        "name": meta.name,
                    }
                )
        return result

    def dispatch(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Dispatch to a registered tool by name."""
        handler = self.get(name)
        if handler is None:
            raise ToolDispatchError(code="UNKNOWN_TOOL", message=f"Unknown tool: {name}")
        return handler(arguments)
