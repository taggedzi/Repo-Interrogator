"""Core adapter protocol and data types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class OutlineSymbol:
    """Single symbol in a source file outline."""

    kind: str
    name: str
    start_line: int
    end_line: int
