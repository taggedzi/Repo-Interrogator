"""Core adapter protocol and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class OutlineSymbol:
    """Single symbol in a source file outline."""

    kind: str
    name: str
    signature: str | None
    start_line: int
    end_line: int
    doc: str | None


class LanguageAdapter(Protocol):
    """Protocol implemented by language adapters."""

    name: str

    def supports_path(self, path: str) -> bool:
        """Return True when adapter supports a file path."""

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Return deterministic symbol outline."""

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Optionally return chunk boundaries as line ranges."""

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Optionally return deterministic symbol hints from prompt text."""
