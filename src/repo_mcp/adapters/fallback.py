"""Lexical fallback adapter for non-Python files."""

from __future__ import annotations

from repo_mcp.adapters.base import OutlineSymbol


class LexicalFallbackAdapter:
    """Default adapter that provides lexical-only behavior."""

    name = "lexical"

    def supports_path(self, path: str) -> bool:
        """Fallback supports any path."""
        _ = path
        return True

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Fallback returns an empty structural outline."""
        _ = path
        _ = text
        return []

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Fallback does not propose chunk boundaries."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Fallback provides no symbol hints."""
        _ = prompt
        return ()
