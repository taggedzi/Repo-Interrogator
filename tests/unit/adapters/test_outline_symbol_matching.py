from __future__ import annotations

from repo_mcp.adapters.base import outline_symbol_matches


def test_outline_symbol_matches_exact_name() -> None:
    assert outline_symbol_matches("Service.run", "Service.run") is True


def test_outline_symbol_matches_short_name_request() -> None:
    assert outline_symbol_matches("Service.run", "run") is True


def test_outline_symbol_matches_qualified_suffix() -> None:
    assert outline_symbol_matches("Service.run", "run") is True
    assert outline_symbol_matches("run", "Service.run") is True


def test_outline_symbol_matches_rejects_unrelated_name() -> None:
    assert outline_symbol_matches("Service.run", "Service.stop") is False
    assert outline_symbol_matches("Service.run", "OtherService.run") is False
