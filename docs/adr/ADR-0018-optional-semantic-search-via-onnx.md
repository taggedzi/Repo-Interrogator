## ADR-0018 - Optional Semantic Search via Local ONNX Model

**Status:** Accepted
**Date:** 2026-06-30

### Context

A usefulness review (live smoke-tested against this repo) found that BM25-only
retrieval has no path to vocabulary-gap matches: a query like "throttle rate
limit" against code that uses different words for the same concept returns
irrelevant noise, because BM25 only matches literal token overlap. `ADR-0009`
declined tree-sitter specifically to avoid new runtime dependencies; this
proposal also adds a dependency, so it revisits that precedent deliberately
rather than by default.

### Decision

Add an **optional** `[semantic]` install extra (`onnxruntime` + `tokenizers`)
that, when installed and a local model is cached, enables `mode="semantic"`
and `mode="hybrid"` on `repo.search`, and an opt-in `retrieval_mode` on
`repo.build_context_bundle`. The core package's `dependencies = []` and
BM25-only behavior are unchanged when the extra is absent.

The model is a single fixed, pinned artifact: a small (~25MB quantized),
Apache-2.0-licensed sentence-embedding model, downloaded once from one
hardcoded source URL + exact revision, SHA256-verified before load, cached
under `data_dir/models/`. The source URL is not user-configurable in v1.

Hybrid fusion uses Reciprocal Rank Fusion (RRF) over BM25 and semantic rank
positions, not a weighted sum of raw scores — this avoids needing to define
score normalization (which would be set-relative and drift as the corpus
changes) and keeps the fusion fully rank-based and deterministic given
deterministic inputs.

### Rationale

- Keeps the zero-dependency core intact; the cost is opt-in, not imposed on
  every user.
- A fixed, checksum-verified model source bounds the supply-chain surface
  to "trust one pinned file," not "trust an arbitrary user-supplied URL."
- RRF avoids inventing a normalization scheme with no principled basis.

### Consequences

- `[semantic]` users take on a real dependency (~tens of MB ONNX runtime +
  model file) and a one-time network fetch.
- Embeddings reuse existing 200-line BM25 chunk boundaries, truncated to the
  model's token window — long chunks are only partially represented in their
  embedding. Documented limitation, not hidden.
- Cross-machine bit-identical float output is not guaranteed; existing
  path/line tie-breaks absorb that the same way they already absorb BM25
  float-scoring jitter.

### Non-goals

- No fine-tuning or custom model training.
- No remote/API-based embedding inference.
- No user-configurable model source in v1.
- No change to default (BM25-only) behavior when the extra is absent.

### Revisit Triggers

- The pinned model is deprecated/removed upstream.
- A demonstrated need arises for a larger or domain-tuned model.
- RRF proves insufficient and a different fusion method is needed.

### Current Status / Known Limitation

`DEFAULT_MODEL_SPEC` (`src/repo_mcp/semantic/model_cache.py`) currently ships
as a deliberate placeholder — a fake URL and all-zero checksums — pending a
maintainer manually resolving a real model commit and computing its real
checksums (see the 4-step instructions in that file). Until that pin lands,
`mode="semantic"`/`"hybrid"` will fail with an explicit download error on
first use rather than silently falling back to BM25, which is correct
fail-closed behavior but means the feature is not yet functional end-to-end.
