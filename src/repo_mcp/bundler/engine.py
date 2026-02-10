"""Deterministic context bundle assembly engine."""

from __future__ import annotations

import hashlib
import time
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass, replace
from typing import Protocol

from repo_mcp.bundler.models import (
    BundleAudit,
    BundleBudget,
    BundleCitation,
    BundleRankingDebugCandidate,
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


class OutlineFn(Protocol):
    """Outline callback signature used by bundler."""

    def __call__(self, path: str) -> list[dict[str, object]]:
        """Return adapter-agnostic outline symbol dictionaries for one path."""


class ReferenceLookupFn(Protocol):
    """Reference lookup callback for deterministic ranking signals."""

    def __call__(self, symbol: str) -> list[dict[str, object]]:
        """Return declaration-linked reference records for one symbol."""


class ReferenceLookupManyFn(Protocol):
    """Batch reference lookup callback for deterministic ranking signals."""

    def __call__(self, symbols: list[str]) -> dict[str, list[object] | tuple[tuple[str, int], ...]]:
        """Return declaration-linked reference records grouped by symbol."""


class ReferenceLookupScopedManyFn(Protocol):
    """Batch reference lookup callback scoped to symbol/path pairs."""

    def __call__(
        self,
        symbol_paths: dict[str, tuple[str, ...]],
    ) -> dict[str, list[object] | tuple[tuple[str, int], ...]]:
        """Return declaration-linked reference records grouped by symbol."""


class BundleProfileSink(Protocol):
    """Optional callback used for targeted bundler profiling payloads."""

    def __call__(self, payload: dict[str, object]) -> None:
        """Consume one deterministic bundler profile payload."""


def build_context_bundle(
    prompt: str,
    budget: BundleBudget,
    search_fn: SearchFn,
    read_lines_fn: ReadLinesFn,
    *,
    include_tests: bool = True,
    strategy: str = "hybrid",
    top_k_per_query: int = 20,
    outline_fn: OutlineFn | None = None,
    reference_lookup_fn: ReferenceLookupFn | None = None,
    reference_lookup_many_fn: ReferenceLookupManyFn | None = None,
    reference_lookup_scoped_many_fn: ReferenceLookupScopedManyFn | None = None,
    profile_sink: BundleProfileSink | None = None,
) -> BundleResult:
    """Build deterministic context bundle using multi-query search and budgets."""
    started = time.perf_counter()
    if budget.max_files < 1:
        raise ValueError("budget.max_files must be >= 1")
    if budget.max_total_lines < 1:
        raise ValueError("budget.max_total_lines must be >= 1")

    prompt_fingerprint = _sha256_hex(prompt)
    queries = _build_queries(prompt)
    prompt_terms = tuple(tokenize(prompt))
    raw_hits: list[_Hit] = []
    symbol_cache: dict[str, tuple[_SymbolRange, ...]] = {}
    for query_index, query in enumerate(queries):
        for hit in search_fn(
            query=query,
            top_k=_query_top_k(
                query_index=query_index,
                base_top_k=top_k_per_query,
            ),
        ):
            candidate = _candidate_from_hit(hit, source_query=query)
            if candidate is None:
                continue
            if not include_tests and _looks_like_test_path(candidate.path):
                continue
            candidate = _align_hit_to_symbol_ranges(
                hit=candidate,
                outline_fn=outline_fn,
                symbol_cache=symbol_cache,
            )
            raw_hits.append(candidate)

    dedupe_started = time.perf_counter()
    deduped = _dedupe_hits(raw_hits)
    dedupe_seconds = time.perf_counter() - dedupe_started

    ranking_started = time.perf_counter()
    ranked = _rank_hits(
        deduped,
        prompt_terms=prompt_terms,
        reference_lookup_fn=reference_lookup_fn,
        reference_lookup_many_fn=reference_lookup_many_fn,
        reference_lookup_scoped_many_fn=reference_lookup_scoped_many_fn,
    )
    ranking_seconds = time.perf_counter() - ranking_started

    budget_started = time.perf_counter()
    selections, totals, budget_notes = _select_with_budget(ranked, budget, read_lines_fn)
    budget_enforcement_seconds = time.perf_counter() - budget_started
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
        ranking_candidate_count=len(ranked),
        ranking_definition_match_count=sum(
            1 for hit in ranked if hit.ranking is not None and hit.ranking.definition_match
        ),
        ranking_reference_proximity_count=sum(
            1
            for hit in ranked
            if hit.ranking is not None and hit.ranking.reference_count_in_range > 0
        ),
        ranking_top_candidates=_build_ranking_debug_candidates(ranked, selections),
    )
    bundle_id = _bundle_id(prompt_fingerprint, selections, totals)
    result = BundleResult(
        bundle_id=bundle_id,
        prompt_fingerprint=prompt_fingerprint,
        strategy=strategy,
        budget=budget,
        totals=totals,
        selections=selections,
        citations=citations,
        audit=audit,
    )
    if profile_sink is not None:
        profile_sink(
            {
                "dedupe_seconds": dedupe_seconds,
                "ranking_seconds": ranking_seconds,
                "budget_enforcement_seconds": budget_enforcement_seconds,
                "total_build_seconds": time.perf_counter() - started,
                "dedupe_before": len(raw_hits),
                "dedupe_after": len(deduped),
                "ranking_candidate_count": len(ranked),
                "selected_excerpt_count": len(selections),
                "selected_file_count": totals.selected_files,
                "budget_skipped_file_count": sum(
                    1 for note in budget_notes if note.startswith("skipped_file_budget:")
                ),
                "budget_skipped_line_count": sum(
                    1 for note in budget_notes if note.startswith("skipped_line_budget:")
                ),
            }
        )
    return result


def _build_queries(prompt: str) -> list[str]:
    keywords = _extract_keywords(prompt)
    return [prompt, *keywords]


def _query_top_k(*, query_index: int, base_top_k: int) -> int:
    """Return deterministic retrieval budget per query for candidate control."""
    if query_index <= 0:
        return max(1, base_top_k)
    keyword_top_k = max(5, base_top_k // 4)
    return min(max(1, base_top_k), keyword_top_k)


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
    aligned_symbol: str | None = None
    ranking: _RankingSignals | None = None


@dataclass(frozen=True, slots=True)
class _RankingSignals:
    definition_match: bool
    reference_count_in_range: int
    min_definition_distance: int
    path_name_relevance: int
    search_score: float
    range_size_penalty: int


@dataclass(frozen=True, slots=True)
class _SymbolRange:
    name: str
    kind: str
    start_line: int
    end_line: int


_ReferenceLineIndex = dict[str, tuple[int, ...]]


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


def _rank_hits(
    hits: list[_Hit],
    *,
    prompt_terms: tuple[str, ...],
    reference_lookup_fn: ReferenceLookupFn | None,
    reference_lookup_many_fn: ReferenceLookupManyFn | None,
    reference_lookup_scoped_many_fn: ReferenceLookupScopedManyFn | None,
) -> list[_Hit]:
    prompt_term_set = frozenset(prompt_terms)
    reference_cache = _prefetch_reference_pairs(
        hits=hits,
        reference_lookup_fn=reference_lookup_fn,
        reference_lookup_many_fn=reference_lookup_many_fn,
        reference_lookup_scoped_many_fn=reference_lookup_scoped_many_fn,
    )
    symbol_token_cache: dict[str, frozenset[str]] = {}
    path_relevance_cache: dict[str, int] = {}
    ranked_hits: list[_Hit] = []
    for hit in hits:
        ranked_hits.append(
            replace(
                hit,
                ranking=_ranking_signals_for_hit(
                    hit,
                    prompt_term_set=prompt_term_set,
                    reference_cache=reference_cache,
                    symbol_token_cache=symbol_token_cache,
                    path_relevance_cache=path_relevance_cache,
                ),
            )
        )
    return sorted(ranked_hits, key=_rank_sort_key)


def _prefetch_reference_pairs(
    *,
    hits: list[_Hit],
    reference_lookup_fn: ReferenceLookupFn | None,
    reference_lookup_many_fn: ReferenceLookupManyFn | None,
    reference_lookup_scoped_many_fn: ReferenceLookupScopedManyFn | None,
) -> dict[str, _ReferenceLineIndex]:
    symbols = sorted(
        {
            hit.aligned_symbol
            for hit in hits
            if hit.aligned_symbol is not None and hit.aligned_symbol.strip()
        }
    )
    if not symbols:
        return {}
    if reference_lookup_scoped_many_fn is not None:
        symbol_paths: dict[str, tuple[str, ...]] = {}
        for symbol in symbols:
            paths = sorted(
                {
                    hit.path
                    for hit in hits
                    if hit.aligned_symbol == symbol and isinstance(hit.path, str) and hit.path
                }
            )
            symbol_paths[symbol] = tuple(paths)
        grouped = reference_lookup_scoped_many_fn(symbol_paths)
        cache: dict[str, _ReferenceLineIndex] = {}
        for symbol in symbols:
            payload = grouped.get(symbol, [])
            cache[symbol] = _build_reference_line_index(payload)
        return cache
    if reference_lookup_many_fn is not None:
        grouped = reference_lookup_many_fn(symbols)
        cache: dict[str, _ReferenceLineIndex] = {}
        for symbol in symbols:
            payload = grouped.get(symbol, [])
            cache[symbol] = _build_reference_line_index(payload)
        return cache
    if reference_lookup_fn is None:
        return {}
    cache: dict[str, _ReferenceLineIndex] = {}
    for symbol in symbols:
        cache[symbol] = _build_reference_line_index(reference_lookup_fn(symbol))
    return cache


def _ranking_signals_for_hit(
    hit: _Hit,
    *,
    prompt_term_set: frozenset[str],
    reference_cache: dict[str, _ReferenceLineIndex],
    symbol_token_cache: dict[str, frozenset[str]],
    path_relevance_cache: dict[str, int],
) -> _RankingSignals:
    aligned_tokens: frozenset[str] = frozenset()
    if hit.aligned_symbol is not None:
        if hit.aligned_symbol in symbol_token_cache:
            aligned_tokens = symbol_token_cache[hit.aligned_symbol]
        else:
            aligned_tokens = frozenset(tokenize(hit.aligned_symbol.replace(".", " ")))
            symbol_token_cache[hit.aligned_symbol] = aligned_tokens
    definition_match = bool(prompt_term_set & aligned_tokens)
    reference_count_in_range = 0
    min_definition_distance = 10**9
    if hit.aligned_symbol is not None:
        references = reference_cache.get(hit.aligned_symbol)
        if references is not None:
            reference_count_in_range, min_definition_distance = _reference_proximity_for_hit(
                hit, references
            )
        else:
            reference_count_in_range = 0
            min_definition_distance = 10**9

    path_name_relevance = path_relevance_cache.get(hit.path)
    if path_name_relevance is None:
        path_name_relevance = _path_name_relevance(hit.path, prompt_term_set)
        path_relevance_cache[hit.path] = path_name_relevance

    return _RankingSignals(
        definition_match=definition_match,
        reference_count_in_range=reference_count_in_range,
        min_definition_distance=min_definition_distance,
        path_name_relevance=path_name_relevance,
        search_score=hit.score,
        range_size_penalty=max(0, hit.end_line - hit.start_line + 1),
    )


def _build_reference_line_index(
    records: list[object] | tuple[tuple[str, int], ...],
) -> _ReferenceLineIndex:
    lines_by_path: dict[str, list[int]] = {}
    for item in records:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], int)
        ):
            path = item[0]
            line = item[1]
            if line < 1:
                continue
            lines_by_path.setdefault(path, []).append(line)
            continue
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        line = item.get("line")
        if not isinstance(path, str):
            continue
        if not isinstance(line, int):
            continue
        if line < 1:
            continue
        lines_by_path.setdefault(path, []).append(line)
    return {
        path: tuple(sorted(lines))
        for path, lines in sorted(lines_by_path.items(), key=lambda item: item[0])
    }


def _reference_proximity_for_hit(hit: _Hit, references: _ReferenceLineIndex) -> tuple[int, int]:
    lines = references.get(hit.path, ())
    if not lines:
        return 0, 10**9
    left = bisect_left(lines, hit.start_line)
    right = bisect_right(lines, hit.end_line)
    count = right - left
    if count > 0:
        return count, 0
    before_distance = 10**9
    after_distance = 10**9
    if left > 0:
        before_distance = hit.start_line - lines[left - 1]
    if left < len(lines):
        after_distance = lines[left] - hit.end_line
    return 0, min(before_distance, after_distance)


def _path_name_relevance(path: str, prompt_terms: frozenset[str]) -> int:
    if not prompt_terms:
        return 0
    path_terms = set(tokenize(path.replace("/", " ").replace(".", " ")))
    return len(path_terms & prompt_terms)


def _rank_sort_key(hit: _Hit) -> tuple[object, ...]:
    ranking = hit.ranking
    if ranking is None:
        raise ValueError("rank_sort_key requires ranking signals")
    return (
        -int(ranking.definition_match),
        -ranking.reference_count_in_range,
        ranking.min_definition_distance,
        -ranking.path_name_relevance,
        -ranking.search_score,
        ranking.range_size_penalty,
        hit.path,
        hit.start_line,
        hit.end_line,
        hit.source_query,
        _candidate_id(hit),
    )


def _candidate_id(hit: _Hit) -> str:
    return f"{hit.path}:{hit.start_line}:{hit.end_line}:{hit.source_query}"


def _build_ranking_debug_candidates(
    ranked: list[_Hit],
    selections: tuple[BundleSelection, ...],
) -> tuple[BundleRankingDebugCandidate, ...]:
    selected_keys = {
        (selection.path, selection.start_line, selection.end_line, selection.source_query)
        for selection in selections
    }
    entries: list[BundleRankingDebugCandidate] = []
    for idx, hit in enumerate(ranked[:20], start=1):
        ranking = hit.ranking
        if ranking is None:
            raise ValueError("ranking debug candidates require ranking signals")
        key = (hit.path, hit.start_line, hit.end_line, hit.source_query)
        entries.append(
            BundleRankingDebugCandidate(
                path=hit.path,
                start_line=hit.start_line,
                end_line=hit.end_line,
                source_query=hit.source_query,
                selected=key in selected_keys,
                rank_position=idx,
                definition_match=ranking.definition_match,
                reference_count_in_range=ranking.reference_count_in_range,
                min_definition_distance=ranking.min_definition_distance,
                path_name_relevance=ranking.path_name_relevance,
                search_score=ranking.search_score,
                range_size_penalty=ranking.range_size_penalty,
            )
        )
    return tuple(entries)


def _align_hit_to_symbol_ranges(
    hit: _Hit,
    outline_fn: OutlineFn | None,
    symbol_cache: dict[str, tuple[_SymbolRange, ...]],
) -> _Hit:
    if outline_fn is None:
        return hit
    ranges = symbol_cache.get(hit.path)
    if ranges is None:
        ranges = _load_symbol_ranges(hit.path, outline_fn)
        symbol_cache[hit.path] = ranges
    if not ranges:
        return hit
    candidates = [
        item
        for item in ranges
        if not (item.end_line < hit.start_line or item.start_line > hit.end_line)
    ]
    if not candidates:
        return hit
    chosen = min(
        candidates,
        key=lambda item: (
            item.end_line - item.start_line,
            item.start_line,
            item.end_line,
            item.name,
            item.kind,
        ),
    )
    return replace(
        hit,
        start_line=chosen.start_line,
        end_line=chosen.end_line,
        aligned_symbol=chosen.name,
    )


def _load_symbol_ranges(path: str, outline_fn: OutlineFn) -> tuple[_SymbolRange, ...]:
    try:
        payload = outline_fn(path)
    except Exception:
        return ()
    ranges: list[_SymbolRange] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        kind = item.get("kind")
        start_line = item.get("start_line")
        end_line = item.get("end_line")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(kind, str) or not kind.strip():
            continue
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            continue
        if start_line < 1 or end_line < start_line:
            continue
        ranges.append(
            _SymbolRange(
                name=name,
                kind=kind,
                start_line=start_line,
                end_line=end_line,
            )
        )
    ranges.sort(key=lambda item: (item.start_line, item.end_line, item.name, item.kind))
    return tuple(ranges)


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
        why_selected = _build_why_selected(hit)
        rationale = _build_rationale(hit)
        selected.append(
            BundleSelection(
                path=hit.path,
                start_line=hit.start_line,
                end_line=hit.end_line,
                excerpt=excerpt,
                why_selected=why_selected,
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
    rationale = (
        f"Selected from query '{hit.source_query}' with score {hit.score:.6f}; "
        f"matched_terms={terms}."
    )
    if hit.aligned_symbol is not None:
        return f"{rationale} aligned_symbol={hit.aligned_symbol}."
    return rationale


def _build_why_selected(hit: _Hit) -> dict[str, object]:
    matched_signals = ["search_score"]
    if hit.matched_terms:
        matched_signals.append("matched_terms")
    ranking = hit.ranking
    if ranking is not None and ranking.definition_match:
        matched_signals.append("definition_match")
    if ranking is not None and ranking.reference_count_in_range > 0:
        matched_signals.append("reference_proximity")
    if hit.aligned_symbol is not None:
        matched_signals.append("aligned_symbol")
    score_components: dict[str, object] = {"search_score": hit.score}
    if ranking is not None:
        score_components = {
            "search_score": ranking.search_score,
            "definition_match": ranking.definition_match,
            "reference_count_in_range": ranking.reference_count_in_range,
            "min_definition_distance": ranking.min_definition_distance,
            "path_name_relevance": ranking.path_name_relevance,
            "range_size_penalty": ranking.range_size_penalty,
        }
    return {
        "matched_signals": matched_signals,
        "score_components": score_components,
        "source_query": hit.source_query,
        "matched_terms": list(hit.matched_terms),
        "symbol_reference": hit.aligned_symbol,
    }


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
