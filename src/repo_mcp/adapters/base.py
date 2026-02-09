"""Core adapter protocol and data types."""

from __future__ import annotations

from dataclasses import dataclass, replace
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


class AdapterContractError(ValueError):
    """Raised when adapter output violates the shared symbol contract."""


def normalize_signature(signature: str | None) -> str | None:
    """Normalize optional signature strings to a stable representation."""
    if signature is None:
        return None
    normalized = signature.strip()
    if not normalized:
        return None
    return normalized


def symbol_sort_key(symbol: OutlineSymbol) -> tuple[int, int, str, str]:
    """Return deterministic sort key for outline symbols."""
    return (symbol.start_line, symbol.end_line, symbol.name, symbol.kind)


def validate_outline_symbols(symbols: list[OutlineSymbol]) -> None:
    """Validate symbols against required invariant fields."""
    for symbol in symbols:
        if not symbol.kind.strip():
            raise AdapterContractError("Outline symbol kind must be non-empty.")
        if not symbol.name.strip():
            raise AdapterContractError("Outline symbol name must be non-empty.")
        if symbol.start_line < 1:
            raise AdapterContractError("Outline symbol start_line must be >= 1.")
        if symbol.end_line < symbol.start_line:
            raise AdapterContractError("Outline symbol end_line must be >= start_line.")


def normalize_and_sort_symbols(symbols: list[OutlineSymbol]) -> list[OutlineSymbol]:
    """Normalize signatures, validate schema invariants, and sort deterministically."""
    normalized = [
        replace(symbol, signature=normalize_signature(symbol.signature)) for symbol in symbols
    ]
    validate_outline_symbols(normalized)
    return sorted(normalized, key=symbol_sort_key)


class LanguageAdapter(Protocol):
    """Protocol implemented by language adapters."""

    name: str

    def supports_path(self, path: str) -> bool:
        """Return True when adapter supports a file path."""

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Return deterministic symbol outline."""

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Optionally return chunk boundaries (chunking hints) as line ranges."""

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Optionally return deterministic symbol hints from prompt text."""
