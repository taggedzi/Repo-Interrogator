"""Deterministic BM25 search over indexed chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
BM25_K1 = 1.2
BM25_B = 0.75


@dataclass(slots=True, frozen=True)
class SearchDocument:
    """Searchable chunk document."""

    path: str
    start_line: int
    end_line: int
    text: str


@dataclass(slots=True, frozen=True)
class SearchHit:
    """Typed BM25 hit output before serialization."""

    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    matched_terms: list[str]


def tokenize(text: str) -> list[str]:
    """Tokenize into deterministic lowercase alphanumeric terms."""
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def bm25_search(documents: list[SearchDocument], query: str, top_k: int) -> list[dict[str, object]]:
    """Return ranked BM25 hits with deterministic tie-breaking."""
    terms = tokenize(query)
    if not terms or not documents or top_k < 1:
        return []

    term_set = set(terms)
    doc_tokens: list[list[str]] = [tokenize(doc.text) for doc in documents]
    doc_lens = [len(tokens) for tokens in doc_tokens]
    avgdl = sum(doc_lens) / len(doc_lens) if doc_lens else 0.0
    if avgdl <= 0:
        return []

    doc_freq: dict[str, int] = {}
    for term in term_set:
        count = 0
        for tokens in doc_tokens:
            if term in tokens:
                count += 1
        doc_freq[term] = count

    scored: list[SearchHit] = []
    total_docs = len(documents)
    for doc, tokens, doc_len in zip(documents, doc_tokens, doc_lens, strict=True):
        token_counts = Counter(tokens)
        score = 0.0
        matched_terms: list[str] = []
        for term in sorted(term_set):
            tf = token_counts.get(term, 0)
            if tf == 0:
                continue
            matched_terms.append(term)
            n_qi = doc_freq.get(term, 0)
            idf = math.log(1.0 + ((total_docs - n_qi + 0.5) / (n_qi + 0.5)))
            denom = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * (doc_len / avgdl))
            score += idf * ((tf * (BM25_K1 + 1.0)) / denom)
        if score <= 0:
            continue
        scored.append(
            SearchHit(
                path=doc.path,
                start_line=doc.start_line,
                end_line=doc.end_line,
                snippet=build_snippet(doc.text),
                score=score,
                matched_terms=matched_terms,
            )
        )

    scored.sort(
        key=lambda hit: (
            -hit.score,
            hit.path,
            hit.start_line,
        )
    )
    return [asdict(hit) for hit in scored[:top_k]]


def build_snippet(text: str) -> str:
    """Build deterministic, bounded snippet."""
    lines = text.splitlines()
    snippet = "\n".join(lines[:3])
    if len(snippet) > 300:
        return snippet[:300]
    return snippet
