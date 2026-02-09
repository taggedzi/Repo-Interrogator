from __future__ import annotations

from repo_mcp.adapters import OutlineSymbol, normalize_and_sort_symbols, symbol_sort_key


def test_symbol_sort_key_orders_start_end_name_kind() -> None:
    symbols = [
        OutlineSymbol(
            kind="method",
            name="B.a",
            signature="()",
            start_line=5,
            end_line=9,
            doc=None,
        ),
        OutlineSymbol(
            kind="class",
            name="A",
            signature="()",
            start_line=5,
            end_line=9,
            doc=None,
        ),
        OutlineSymbol(
            kind="function",
            name="z",
            signature="()",
            start_line=5,
            end_line=8,
            doc=None,
        ),
        OutlineSymbol(
            kind="function",
            name="a",
            signature="()",
            start_line=4,
            end_line=6,
            doc=None,
        ),
    ]

    sorted_symbols = sorted(symbols, key=symbol_sort_key)

    assert [item.name for item in sorted_symbols] == ["a", "z", "A", "B.a"]


def test_normalize_and_sort_symbols_breaks_name_ties_by_kind() -> None:
    symbols = [
        OutlineSymbol(
            kind="method",
            name="Service.run",
            signature="()",
            start_line=8,
            end_line=8,
            doc=None,
        ),
        OutlineSymbol(
            kind="async_method",
            name="Service.run",
            signature="()",
            start_line=8,
            end_line=8,
            doc=None,
        ),
    ]

    normalized = normalize_and_sort_symbols(symbols)

    assert [item.kind for item in normalized] == ["async_method", "method"]
