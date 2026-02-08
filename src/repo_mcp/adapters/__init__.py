"""Language adapter interfaces."""

from .base import LanguageAdapter, OutlineSymbol
from .fallback import LexicalFallbackAdapter
from .registry import AdapterRegistry

__all__ = ["AdapterRegistry", "LanguageAdapter", "LexicalFallbackAdapter", "OutlineSymbol"]
