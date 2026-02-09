"""Language adapter interfaces."""

from .base import (
    AdapterContractError,
    LanguageAdapter,
    OutlineSymbol,
    normalize_and_sort_symbols,
    normalize_signature,
    symbol_sort_key,
    validate_outline_symbols,
)
from .fallback import LexicalFallbackAdapter
from .python import PythonAstAdapter
from .registry import AdapterRegistry
from .runtime import build_adapter_registry

__all__ = [
    "AdapterRegistry",
    "AdapterContractError",
    "LanguageAdapter",
    "LexicalFallbackAdapter",
    "OutlineSymbol",
    "PythonAstAdapter",
    "build_adapter_registry",
    "normalize_and_sort_symbols",
    "normalize_signature",
    "symbol_sort_key",
    "validate_outline_symbols",
]
