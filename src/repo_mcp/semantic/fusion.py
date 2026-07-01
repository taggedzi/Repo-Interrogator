"""Cosine-similarity semantic search and Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

import math

RRF_K = 60


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Return cosine similarity, treating any zero-length vector as zero similarity."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_search(
    *,
    query_vector: tuple[float, ...],
    chunk_vectors: dict[str, tuple[float, ...]],
    chunk_metadata: dict[str, dict[str, object]],
    top_k: int,
) -> list[dict[str, object]]:
    """Rank chunks by cosine similarity to query_vector, deterministically tie-broken."""
    scored: list[tuple[float, str, str, int]] = []
    for chunk_id, vector in chunk_vectors.items():
        metadata = chunk_metadata.get(chunk_id)
        if metadata is None:
            continue
        score = cosine_similarity(query_vector, vector)
        path = str(metadata["path"])
        start_line = int(metadata["start_line"])  # type: ignore[call-overload]
        scored.append((score, path, chunk_id, start_line))

    scored.sort(key=lambda item: (-item[0], item[1], item[3]))

    hits: list[dict[str, object]] = []
    for score, path, chunk_id, start_line in scored[:top_k]:
        metadata = chunk_metadata[chunk_id]
        hits.append(
            {
                "path": path,
                "start_line": start_line,
                "end_line": metadata["end_line"],
                "snippet": metadata.get("snippet", ""),
                "score": score,
                "matched_terms": [],
            }
        )
    return hits


def reciprocal_rank_fusion(
    bm25_hits: list[dict[str, object]],
    semantic_hits: list[dict[str, object]],
    *,
    top_k: int,
    k: int = RRF_K,
) -> list[dict[str, object]]:
    """Fuse two ranked hit lists by rank position (RRF), not raw score.

    Each list is assumed already sorted best-first (as both bm25_search and
    semantic_search already return). A candidate identified by
    (path, start_line, end_line) earns 1/(k + rank) from each list it
    appears in (rank is 1-based); lists it's absent from contribute 0.
    """
    rrf_scores: dict[tuple[str, int, int], float] = {}
    by_key: dict[tuple[str, int, int], dict[str, object]] = {}

    for source_hits in (bm25_hits, semantic_hits):
        for rank, hit in enumerate(source_hits, start=1):
            key = (str(hit["path"]), int(hit["start_line"]), int(hit["end_line"]))  # type: ignore[call-overload]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in by_key:
                by_key[key] = hit
            else:
                existing = by_key[key]
                merged_terms = sorted(
                    set(existing.get("matched_terms", []) or [])  # type: ignore[call-overload]
                    | set(hit.get("matched_terms", []) or [])  # type: ignore[call-overload]
                )
                by_key[key] = {**existing, "matched_terms": merged_terms}

    ordered_keys = sorted(
        rrf_scores.keys(),
        key=lambda key: (-rrf_scores[key], key[0], key[1], key[2]),
    )
    fused: list[dict[str, object]] = []
    for key in ordered_keys[:top_k]:
        base = by_key[key]
        fused.append({**base, "score": rrf_scores[key]})
    return fused
