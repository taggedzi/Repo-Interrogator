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
    parent_symbol: str | None = None
    scope_kind: str | None = None
    is_conditional: bool | None = None
    decl_context: str | None = None


@dataclass(slots=True, frozen=True)
class SymbolReference:
    """Single cross-file symbol reference record."""

    symbol: str
    path: str
    line: int
    kind: str
    evidence: str
    strategy: str
    confidence: str


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


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional text fields to stable string-or-None values."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def symbol_sort_key(symbol: OutlineSymbol) -> tuple[int, int, str, str]:
    """Return deterministic sort key for outline symbols."""
    return (symbol.start_line, symbol.end_line, symbol.name, symbol.kind)


def validate_outline_symbols(symbols: list[OutlineSymbol]) -> None:
    """Validate symbols against required invariant fields."""
    allowed_scope_kinds = {"module", "class", "function"}
    for symbol in symbols:
        if not symbol.kind.strip():
            raise AdapterContractError("Outline symbol kind must be non-empty.")
        if not symbol.name.strip():
            raise AdapterContractError("Outline symbol name must be non-empty.")
        if symbol.start_line < 1:
            raise AdapterContractError("Outline symbol start_line must be >= 1.")
        if symbol.end_line < symbol.start_line:
            raise AdapterContractError("Outline symbol end_line must be >= start_line.")
        if symbol.scope_kind is not None and symbol.scope_kind not in allowed_scope_kinds:
            raise AdapterContractError(
                "Outline symbol scope_kind must be one of module, class, function."
            )


def reference_sort_key(reference: SymbolReference) -> tuple[str, int, str, str]:
    """Return deterministic sort key for symbol references."""
    return (reference.path, reference.line, reference.symbol, reference.kind)


def validate_symbol_references(references: list[SymbolReference]) -> None:
    """Validate references against required invariant fields."""
    allowed_confidence = {"high", "medium", "low"}
    allowed_strategy = {"ast", "lexical"}
    for reference in references:
        if not reference.symbol.strip():
            raise AdapterContractError("Symbol reference symbol must be non-empty.")
        if not reference.path.strip():
            raise AdapterContractError("Symbol reference path must be non-empty.")
        if reference.line < 1:
            raise AdapterContractError("Symbol reference line must be >= 1.")
        if not reference.kind.strip():
            raise AdapterContractError("Symbol reference kind must be non-empty.")
        if not reference.evidence.strip():
            raise AdapterContractError("Symbol reference evidence must be non-empty.")
        if reference.strategy not in allowed_strategy:
            raise AdapterContractError("Symbol reference strategy must be one of ast, lexical.")
        if reference.confidence not in allowed_confidence:
            raise AdapterContractError("Symbol reference confidence must be high, medium, or low.")


def normalize_and_sort_symbols(symbols: list[OutlineSymbol]) -> list[OutlineSymbol]:
    """Normalize signatures, validate schema invariants, and sort deterministically."""
    normalized = [_normalize_symbol(symbol) for symbol in symbols]
    validate_outline_symbols(normalized)
    return sorted(normalized, key=symbol_sort_key)


def normalize_and_sort_references(references: list[SymbolReference]) -> list[SymbolReference]:
    """Validate schema invariants and sort references deterministically."""
    normalized = [
        replace(
            reference,
            symbol=normalize_optional_text(reference.symbol) or "",
            path=normalize_optional_text(reference.path) or "",
            kind=normalize_optional_text(reference.kind) or "",
            evidence=normalize_optional_text(reference.evidence) or "",
            strategy=normalize_optional_text(reference.strategy) or "",
            confidence=normalize_optional_text(reference.confidence) or "",
        )
        for reference in references
    ]
    validate_symbol_references(normalized)
    return sorted(normalized, key=reference_sort_key)


def _normalize_symbol(symbol: OutlineSymbol) -> OutlineSymbol:
    normalized_scope_kind = normalize_optional_text(symbol.scope_kind)
    inferred_scope_kind = normalized_scope_kind or _infer_scope_kind(symbol.kind)
    normalized_parent = normalize_optional_text(symbol.parent_symbol)
    inferred_parent = normalized_parent or _infer_parent_symbol(
        name=symbol.name,
        scope_kind=inferred_scope_kind,
    )
    return replace(
        symbol,
        signature=normalize_signature(symbol.signature),
        parent_symbol=inferred_parent,
        scope_kind=inferred_scope_kind,
        decl_context=normalize_optional_text(symbol.decl_context),
    )


def _infer_scope_kind(kind: str) -> str:
    if kind in {"method", "async_method", "constructor"}:
        return "class"
    return "module"


def _infer_parent_symbol(name: str, scope_kind: str | None) -> str | None:
    if scope_kind != "class":
        return None
    if "." not in name:
        return None
    parent, _ = name.rsplit(".", 1)
    return parent or None


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
