"""Runtime adapter registry construction."""

from __future__ import annotations

from repo_mcp.adapters.fallback import LexicalFallbackAdapter
from repo_mcp.adapters.go import GoLexicalAdapter
from repo_mcp.adapters.java import JavaLexicalAdapter
from repo_mcp.adapters.python import PythonAstAdapter
from repo_mcp.adapters.registry import AdapterRegistry
from repo_mcp.adapters.rust import RustLexicalAdapter
from repo_mcp.adapters.ts_js import TypeScriptJavaScriptLexicalAdapter
from repo_mcp.config import ServerConfig


def build_adapter_registry(config: ServerConfig) -> AdapterRegistry:
    """Build adapter registry from effective config."""
    registry = AdapterRegistry()
    if config.adapters.python_enabled:
        registry.register(PythonAstAdapter())
    registry.register(GoLexicalAdapter())
    registry.register(JavaLexicalAdapter())
    registry.register(RustLexicalAdapter())
    registry.register(TypeScriptJavaScriptLexicalAdapter())
    registry.register(LexicalFallbackAdapter(), fallback=True)
    return registry
