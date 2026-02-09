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
from .cpp import CppLexicalAdapter
from .csharp import CSharpLexicalAdapter
from .fallback import LexicalFallbackAdapter
from .go import GoLexicalAdapter
from .java import JavaLexicalAdapter
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
from .rust import RustLexicalAdapter
from .ts_js import TypeScriptJavaScriptLexicalAdapter

__all__ = [
    "AdapterRegistry",
    "AdapterContractError",
    "CppLexicalAdapter",
    "CSharpLexicalAdapter",
    "LanguageAdapter",
    "LexicalFallbackAdapter",
    "GoLexicalAdapter",
    "JavaLexicalAdapter",
    "LexicalRules",
    "LexicalToken",
    "OutlineSymbol",
    "PythonAstAdapter",
    "RustLexicalAdapter",
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
