"""Typed models for deterministic context bundles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BundleBudget:
    """Context bundle budget constraints."""

    max_files: int
    max_total_lines: int


@dataclass(slots=True, frozen=True)
class BundleSelection:
    """Selected excerpt with rationale and ranking metadata."""

    path: str
    start_line: int
    end_line: int
    excerpt: str
    rationale: str
    score: float
    source_query: str


@dataclass(slots=True, frozen=True)
class BundleCitation:
    """Citation metadata for one selected excerpt."""

    path: str
    start_line: int
    end_line: int
    selection_index: int


@dataclass(slots=True, frozen=True)
class BundleTotals:
    """Bundle totals and truncation metadata."""

    selected_files: int
    selected_lines: int
    truncated: bool


@dataclass(slots=True, frozen=True)
class BundleAudit:
    """Deterministic audit details for bundling decisions."""

    search_queries: tuple[str, ...]
    dedupe_before: int
    dedupe_after: int
    budget_enforcement: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class BundleResult:
    """Final deterministic bundle artifact."""

    bundle_id: str
    prompt_fingerprint: str
    strategy: str
    budget: BundleBudget
    totals: BundleTotals
    selections: tuple[BundleSelection, ...]
    citations: tuple[BundleCitation, ...]
    audit: BundleAudit
