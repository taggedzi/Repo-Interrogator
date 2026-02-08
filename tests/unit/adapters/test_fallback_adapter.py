from __future__ import annotations

from repo_mcp.adapters import LexicalFallbackAdapter


def test_fallback_adapter_supports_any_path_and_returns_empty_outline() -> None:
    adapter = LexicalFallbackAdapter()

    assert adapter.supports_path("src/main.py")
    assert adapter.supports_path("docs/readme.md")
    assert adapter.outline("src/main.py", "def x():\n    pass\n") == []


def test_fallback_adapter_optional_hooks_return_none_or_empty() -> None:
    adapter = LexicalFallbackAdapter()

    assert adapter.smart_chunks("a.txt", "one\ntwo\n") is None
    assert adapter.symbol_hints("find parser function") == ()
