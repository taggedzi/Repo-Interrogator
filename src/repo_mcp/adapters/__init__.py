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
from .lexical import (
    BraceBlock,
    BraceScanResult,
    LexicalRules,
    LexicalToken,
    extract_identifier_tokens,
    mask_comments_and_strings,
    scan_brace_blocks,
)
from .python import PythonAstAdapter
from .registry import AdapterRegistry
from .runtime import build_adapter_registry
from .ts_js import TypeScriptJavaScriptLexicalAdapter

__all__ = [
    "AdapterRegistry",
    "AdapterContractError",
    "LanguageAdapter",
    "LexicalFallbackAdapter",
    "LexicalRules",
    "LexicalToken",
    "OutlineSymbol",
    "PythonAstAdapter",
    "TypeScriptJavaScriptLexicalAdapter",
    "BraceBlock",
    "BraceScanResult",
    "build_adapter_registry",
    "extract_identifier_tokens",
    "mask_comments_and_strings",
    "normalize_and_sort_symbols",
    "normalize_signature",
    "scan_brace_blocks",
    "symbol_sort_key",
    "validate_outline_symbols",
]
