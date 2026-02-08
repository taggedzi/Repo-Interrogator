"""Adapter registry with deterministic selection behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

from repo_mcp.adapters.base import LanguageAdapter


@dataclass(slots=True)
class AdapterRegistry:
    """Ordered adapter registry with explicit fallback adapter."""

    _adapters: list[LanguageAdapter] = field(default_factory=list)
    _fallback: LanguageAdapter | None = None

    def register(self, adapter: LanguageAdapter, *, fallback: bool = False) -> None:
        """Register an adapter in deterministic insertion order."""
        if fallback:
            self._fallback = adapter
            return
        self._adapters.append(adapter)

    def select(self, path: str) -> LanguageAdapter:
        """Select the first adapter that supports the path, else fallback."""
        for adapter in self._adapters:
            if adapter.supports_path(path):
                return adapter
        if self._fallback is not None:
            return self._fallback
        raise LookupError(f"No adapter supports path: {path}")

    def names(self) -> tuple[str, ...]:
        """Return registered adapter names in deterministic order."""
        ordered = [adapter.name for adapter in self._adapters]
        if self._fallback is not None:
            ordered.append(self._fallback.name)
        return tuple(ordered)
