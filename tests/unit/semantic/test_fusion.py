from __future__ import annotations

from repo_mcp.semantic.fusion import cosine_similarity, reciprocal_rank_fusion, semantic_search


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == 0.0


def test_cosine_similarity_zero_vector_is_zero_not_nan() -> None:
    assert cosine_similarity((0.0, 0.0), (1.0, 0.0)) == 0.0


def test_semantic_search_ranks_by_cosine_similarity_desc() -> None:
    chunk_vectors = {
        "id-close": (1.0, 0.0),
        "id-far": (0.0, 1.0),
    }
    chunk_metadata = {
        "id-close": {"path": "a.py", "start_line": 1, "end_line": 5, "snippet": "a"},
        "id-far": {"path": "b.py", "start_line": 1, "end_line": 5, "snippet": "b"},
    }

    hits = semantic_search(
        query_vector=(1.0, 0.0),
        chunk_vectors=chunk_vectors,
        chunk_metadata=chunk_metadata,
        top_k=10,
    )

    assert [hit["path"] for hit in hits] == ["a.py", "b.py"]
    assert hits[0]["score"] > hits[1]["score"]


def test_semantic_search_breaks_ties_by_path_then_start_line() -> None:
    chunk_vectors = {
        "id-1": (1.0, 0.0),
        "id-2": (1.0, 0.0),
    }
    chunk_metadata = {
        "id-1": {"path": "b.py", "start_line": 1, "end_line": 5, "snippet": "b"},
        "id-2": {"path": "a.py", "start_line": 1, "end_line": 5, "snippet": "a"},
    }

    hits = semantic_search(
        query_vector=(1.0, 0.0),
        chunk_vectors=chunk_vectors,
        chunk_metadata=chunk_metadata,
        top_k=10,
    )

    assert [hit["path"] for hit in hits] == ["a.py", "b.py"]


def test_reciprocal_rank_fusion_favors_items_ranked_high_in_both_lists() -> None:
    bm25_hits = [
        {
            "path": "shared.py",
            "start_line": 1,
            "end_line": 5,
            "score": 10.0,
            "snippet": "",
            "matched_terms": ["x"],
        },
        {
            "path": "bm25_only.py",
            "start_line": 1,
            "end_line": 5,
            "score": 5.0,
            "snippet": "",
            "matched_terms": ["x"],
        },
    ]
    semantic_hits = [
        {
            "path": "shared.py",
            "start_line": 1,
            "end_line": 5,
            "score": 0.9,
            "snippet": "",
            "matched_terms": [],
        },
        {
            "path": "semantic_only.py",
            "start_line": 1,
            "end_line": 5,
            "score": 0.8,
            "snippet": "",
            "matched_terms": [],
        },
    ]

    fused = reciprocal_rank_fusion(bm25_hits, semantic_hits, top_k=10)

    assert fused[0]["path"] == "shared.py"
    assert {hit["path"] for hit in fused} == {"shared.py", "bm25_only.py", "semantic_only.py"}


def test_reciprocal_rank_fusion_respects_top_k() -> None:
    bm25_hits = [
        {
            "path": f"f{i}.py",
            "start_line": 1,
            "end_line": 5,
            "score": float(10 - i),
            "snippet": "",
            "matched_terms": [],
        }
        for i in range(5)
    ]
    fused = reciprocal_rank_fusion(bm25_hits, [], top_k=2)
    assert len(fused) == 2


def test_reciprocal_rank_fusion_is_deterministic() -> None:
    bm25_hits = [
        {
            "path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "score": 1.0,
            "snippet": "",
            "matched_terms": [],
        },
        {
            "path": "b.py",
            "start_line": 1,
            "end_line": 5,
            "score": 1.0,
            "snippet": "",
            "matched_terms": [],
        },
    ]
    first = reciprocal_rank_fusion(bm25_hits, [], top_k=10)
    second = reciprocal_rank_fusion(bm25_hits, [], top_k=10)
    assert first == second
