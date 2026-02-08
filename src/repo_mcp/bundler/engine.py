"""Deterministic context bundle assembly engine."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Protocol

from repo_mcp.bundler.models import (
    BundleAudit,
    BundleBudget,
    BundleCitation,
    BundleResult,
    BundleSelection,
    BundleTotals,
)
from repo_mcp.index.search import tokenize


class SearchFn(Protocol):
    """Search callback signature used by bundler."""

    def __call__(
        self,
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        """Return search hits."""


class ReadLinesFn(Protocol):
    """Line-reader callback signature used by bundler."""

    def __call__(self, path: str, start_line: int, end_line: int) -> list[str]:
        """Return text lines for an inclusive range."""


def build_context_bundle(
    prompt: str,
    budget: BundleBudget,
    search_fn: SearchFn,
    read_lines_fn: ReadLinesFn,
    *,
    include_tests: bool = True,
    strategy: str = "hybrid",
    top_k_per_query: int = 20,
) -> BundleResult:
    """Build deterministic context bundle using multi-query search and budgets."""
    if budget.max_files < 1:
        raise ValueError("budget.max_files must be >= 1")
    if budget.max_total_lines < 1:
        raise ValueError("budget.max_total_lines must be >= 1")

    prompt_fingerprint = _sha256_hex(prompt)
    queries = _build_queries(prompt)
    raw_hits: list[_Hit] = []
    for query in queries:
        for hit in search_fn(query=query, top_k=top_k_per_query):
            candidate = _candidate_from_hit(hit, source_query=query)
            if candidate is None:
                continue
            if not include_tests and _looks_like_test_path(candidate.path):
                continue
            raw_hits.append(candidate)

    deduped = _dedupe_hits(raw_hits)
    ranked = sorted(deduped, key=lambda item: (-item.score, item.path, item.start_line))
    selections, totals, budget_notes = _select_with_budget(ranked, budget, read_lines_fn)
    citations = tuple(
        BundleCitation(
            path=selection.path,
            start_line=selection.start_line,
            end_line=selection.end_line,
            selection_index=index,
        )
        for index, selection in enumerate(selections)
    )

    audit = BundleAudit(
        search_queries=tuple(queries),
        dedupe_before=len(raw_hits),
        dedupe_after=len(deduped),
        budget_enforcement=tuple(budget_notes),
    )
    bundle_id = _bundle_id(prompt_fingerprint, selections, totals)
    return BundleResult(
        bundle_id=bundle_id,
        prompt_fingerprint=prompt_fingerprint,
        strategy=strategy,
        budget=budget,
        totals=totals,
        selections=selections,
        citations=citations,
        audit=audit,
    )


def _build_queries(prompt: str) -> list[str]:
    keywords = _extract_keywords(prompt)
    return [prompt, *keywords]


def _extract_keywords(prompt: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokenize(prompt):
        if len(token) < 3:
            continue
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
        if len(ordered) >= 8:
            break
    return ordered


def _candidate_from_hit(hit: dict[str, object], source_query: str) -> _Hit | None:
    path = hit.get("path")
    start_line = hit.get("start_line")
    end_line = hit.get("end_line")
    score = hit.get("score")
    matched_terms_raw = hit.get("matched_terms", [])
    if not isinstance(path, str):
        return None
    if not isinstance(start_line, int):
        return None
    if not isinstance(end_line, int):
        return None
    if not isinstance(score, float):
        return None
    matched_terms: list[str] = []
    if isinstance(matched_terms_raw, list):
        for item in matched_terms_raw:
            if isinstance(item, str):
                matched_terms.append(item)
    return _Hit(
        path=path,
        start_line=start_line,
        end_line=end_line,
        score=score,
        source_query=source_query,
        matched_terms=tuple(sorted(set(matched_terms))),
    )


@dataclass(frozen=True, slots=True)
class _Hit:
    path: str
    start_line: int
    end_line: int
    score: float
    source_query: str
    matched_terms: tuple[str, ...]


def _dedupe_hits(hits: list[_Hit]) -> list[_Hit]:
    best_by_key: dict[tuple[str, int, int], _Hit] = {}
    for hit in hits:
        key = (hit.path, hit.start_line, hit.end_line)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = hit
            continue
        if hit.score > current.score:
            best_by_key[key] = hit
            continue
        if hit.score == current.score and hit.source_query < current.source_query:
            best_by_key[key] = hit
    keys = sorted(best_by_key.keys(), key=lambda item: (item[0], item[1], item[2]))
    return [best_by_key[key] for key in keys]


def _select_with_budget(
    hits: list[_Hit],
    budget: BundleBudget,
    read_lines_fn: ReadLinesFn,
) -> tuple[tuple[BundleSelection, ...], BundleTotals, list[str]]:
    selected: list[BundleSelection] = []
    selected_paths: set[str] = set()
    total_lines = 0
    truncated = False
    notes: list[str] = []

    for hit in hits:
        line_count = max(0, hit.end_line - hit.start_line + 1)
        if line_count == 0:
            notes.append(f"skipped_zero_lines:{hit.path}:{hit.start_line}-{hit.end_line}")
            continue
        next_total = total_lines + line_count
        next_file_count = len(selected_paths) + (0 if hit.path in selected_paths else 1)
        if next_file_count > budget.max_files:
            truncated = True
            notes.append(f"skipped_file_budget:{hit.path}:{hit.start_line}-{hit.end_line}")
            continue
        if next_total > budget.max_total_lines:
            truncated = True
            notes.append(f"skipped_line_budget:{hit.path}:{hit.start_line}-{hit.end_line}")
            continue

        lines = read_lines_fn(hit.path, hit.start_line, hit.end_line)
        excerpt = "\n".join(lines)
        rationale = _build_rationale(hit)
        selected.append(
            BundleSelection(
                path=hit.path,
                start_line=hit.start_line,
                end_line=hit.end_line,
                excerpt=excerpt,
                rationale=rationale,
                score=hit.score,
                source_query=hit.source_query,
            )
        )
        selected_paths.add(hit.path)
        total_lines = next_total

    totals = BundleTotals(
        selected_files=len(selected_paths),
        selected_lines=total_lines,
        truncated=truncated,
    )
    return tuple(selected), totals, notes


def _build_rationale(hit: _Hit) -> str:
    terms = ", ".join(hit.matched_terms) if hit.matched_terms else "none"
    return (
        f"Selected from query '{hit.source_query}' with score {hit.score:.6f}; "
        f"matched_terms={terms}."
    )


def _bundle_id(
    prompt_fingerprint: str,
    selections: tuple[BundleSelection, ...],
    totals: BundleTotals,
) -> str:
    digest = hashlib.sha256()
    digest.update(prompt_fingerprint.encode("ascii"))
    digest.update(b"|")
    digest.update(str(totals.selected_files).encode("ascii"))
    digest.update(b"|")
    digest.update(str(totals.selected_lines).encode("ascii"))
    digest.update(b"|")
    digest.update(str(totals.truncated).encode("ascii"))
    for selection in selections:
        payload = asdict(selection)
        digest.update(repr(payload).encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _looks_like_test_path(path: str) -> bool:
    lowered = path.lower()
    return (
        "/tests/" in f"/{lowered}/" or lowered.startswith("tests/") or lowered.endswith("_test.py")
    )
