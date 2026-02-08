from __future__ import annotations

from dataclasses import dataclass

from repo_mcp.adapters import AdapterRegistry, LexicalFallbackAdapter


@dataclass(slots=True)
class PrefixAdapter:
    name: str
    prefix: str

    def supports_path(self, path: str) -> bool:
        return path.startswith(self.prefix)

    def outline(self, path: str, text: str) -> list[object]:
        _ = path
        _ = text
        return []

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        _ = prompt
        return ()


def test_registry_selects_first_matching_adapter_in_registration_order() -> None:
    registry = AdapterRegistry()
    registry.register(PrefixAdapter(name="first-src", prefix="src/"))
    registry.register(PrefixAdapter(name="second-src", prefix="src/"))
    registry.register(LexicalFallbackAdapter(), fallback=True)

    selected = registry.select("src/main.py")

    assert selected.name == "first-src"
    assert registry.names() == ("first-src", "second-src", "lexical")


def test_registry_uses_fallback_for_non_matching_path() -> None:
    registry = AdapterRegistry()
    registry.register(PrefixAdapter(name="python-only", prefix="pkg/"))
    registry.register(LexicalFallbackAdapter(), fallback=True)

    selected = registry.select("docs/readme.md")

    assert selected.name == "lexical"
