"""MCP tool interfaces and registrations."""

from .registry import ToolDispatchError, ToolHandler, ToolRegistry

__all__ = ["ToolDispatchError", "ToolHandler", "ToolRegistry"]
