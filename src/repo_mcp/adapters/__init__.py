"""Language adapter interfaces."""

from .base import LanguageAdapter, OutlineSymbol
from .fallback import LexicalFallbackAdapter
from .python import PythonAstAdapter
from .registry import AdapterRegistry
from .runtime import build_adapter_registry

__all__ = [
    "AdapterRegistry",
    "LanguageAdapter",
    "LexicalFallbackAdapter",
    "OutlineSymbol",
    "PythonAstAdapter",
    "build_adapter_registry",
]
