from __future__ import annotations

import pytest

from repo_mcp.adapters import (
    AdapterContractError,
    OutlineSymbol,
    normalize_and_sort_symbols,
    normalize_signature,
    validate_outline_symbols,
)


def test_validate_outline_symbols_accepts_valid_symbol_set() -> None:
    symbols = [
        OutlineSymbol(
            kind="function",
            name="build",
            signature="(name: str)",
            start_line=10,
            end_line=14,
            doc=None,
        )
    ]

    validate_outline_symbols(symbols)


@pytest.mark.parametrize(
    ("symbol", "message"),
    [
        (
            OutlineSymbol(
                kind="",
                name="build",
                signature=None,
                start_line=1,
                end_line=1,
                doc=None,
            ),
            "kind",
        ),
        (
            OutlineSymbol(
                kind="function",
                name="   ",
                signature=None,
                start_line=1,
                end_line=1,
                doc=None,
            ),
            "name",
        ),
        (
            OutlineSymbol(
                kind="function",
                name="build",
                signature=None,
                start_line=0,
                end_line=1,
                doc=None,
            ),
            "start_line",
        ),
        (
            OutlineSymbol(
                kind="function",
                name="build",
                signature=None,
                start_line=7,
                end_line=6,
                doc=None,
            ),
            "end_line",
        ),
    ],
)
def test_validate_outline_symbols_rejects_invalid_symbols(
    symbol: OutlineSymbol,
    message: str,
) -> None:
    with pytest.raises(AdapterContractError, match=message):
        validate_outline_symbols([symbol])


def test_normalize_signature_returns_trimmed_or_none() -> None:
    assert normalize_signature(None) is None
    assert normalize_signature("   ") is None
    assert normalize_signature("  (x: int)  ") == "(x: int)"


def test_normalize_and_sort_symbols_normalizes_and_orders() -> None:
    symbols = [
        OutlineSymbol(
            kind="method",
            name="Worker.run",
            signature="   (self)   ",
            start_line=12,
            end_line=12,
            doc=None,
        ),
        OutlineSymbol(
            kind="class",
            name="Worker",
            signature="()",
            start_line=4,
            end_line=20,
            doc=None,
        ),
    ]

    normalized = normalize_and_sort_symbols(symbols)

    assert [item.name for item in normalized] == ["Worker", "Worker.run"]
    assert normalized[1].signature == "(self)"
