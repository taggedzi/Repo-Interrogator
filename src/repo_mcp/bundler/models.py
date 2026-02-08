"""Typed models for context bundles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BundleSelection:
    """Represents an included excerpt within a context bundle."""

    path: str
    start_line: int
    end_line: int
    rationale: str
