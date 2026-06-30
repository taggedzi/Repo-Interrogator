# Design: Reference Conformance & Optional Semantic Search

Date: 2026-06-30
Status: Approved (pending implementation planning)

## Background

A usefulness review of the MCP server (live smoke-tested against this repo, not just spec-read)
found two concrete gaps in how well the server helps an AI assemble accurate task context:

1. **Lexical-only retrieval has no path to vocabulary-gap matches.** `repo.search` is pure BM25.
   Querying `"throttle rate limit"` against this codebase (which uses different vocabulary)
   returned irrelevant noise matched on isolated common tokens, not on a query-vs-meaning gap.
2. **`repo.references` misses real, live usages, and there is no definition-finder.**
   `repo.references` for `_rank_sort_key` returned zero hits despite a real usage at
   `src/repo_mcp/bundler/engine.py:356` (`sorted(ranked_hits, key=_rank_sort_key)`), because the
   Python adapter's reference collector only classifies `import`/`call`/`inheritance`/
   `instantiation` usages, not bare name reads. SPEC.md §10.4 already lists `read`/`write` as
   expected reference kinds — this is a conformance gap, not a new feature. Separately, there is
   no way to ask "where is symbol X declared" without scanning per-file outlines.

This document covers two independent tracks that close both gaps. They can be planned and shipped
separately.

## Track A: Reference conformance + `repo.find_definition`

**Scope:** zero new dependencies, no SPEC non-goal changes, pure AST work in the existing Python
adapter plus one new tool.

### A1. Close the missed-usage gap

`_PythonReferenceCollector` (`src/repo_mcp/adapters/python.py:289`) currently only visits
`Import`, `ImportFrom`, `ClassDef` bases, and `Call`. Add:

- `visit_Name` for `Load` context → emits a `read` reference. This is the fix for the demonstrated
  bug (`key=_rank_sort_key`), and incidentally makes bare `@decorator` usage (no parens) visible
  for the first time, since that was previously an unclassified Name-load site.
- `visit_Name` for `Store` context, only when the assigned name matches an already-known declared
  symbol (rebinding) → emits a `write` reference.

**Required invariant:** no double-counting. A `Call`'s function name and a `ClassDef`'s base name
are already classified as `call`/`inheritance` by the existing specialized visitors; those specific
Name nodes must be excluded from the generic `read` pass so each usage site produces exactly one
reference.

**Confidence:** bare-name `read`/`write` matches get `"low"` confidence (vs. `"high"`/`"medium"`
for imports/qualified calls) — unscoped name matching has real false-positive risk (e.g. a local
variable that happens to share a name with an unrelated module-level symbol), and that risk should
be visible to the caller rather than hidden behind a uniform confidence value.

### A2. New tool `repo.find_definition`

- **Input:** `symbol` (string, required), `path` (string, optional scope), `top_k` (optional,
  bounded like existing `max_references`).
- **Output:** bounded list of `{path, start_line, end_line, kind, signature, scope_kind}`,
  sourced from `OutlineSymbol` entries whose name matches the requested symbol. Sorted `path`
  ascending then `start_line` ascending (consistent with existing tie-break conventions).
- **No disambiguation beyond syntax:** if a name is declared in multiple places, all are returned,
  consistent with `outline()`'s existing "syntactic facts only" philosophy.
- **Requires a declaration index:** `symbol_name → [(path, OutlineSymbol)]`, built by running
  `outline()` (AST for Python, lexical for other languages — same strategy split `repo.references`
  already uses) over all indexed files. This extends `IndexManager`'s existing file-hash-based
  incremental refresh rather than introducing a separate subsystem — only changed files' symbols
  are recomputed on refresh.

### Error handling

Unknown symbol → empty list, not an error (consistent with `repo.references` today). Existing
path/policy sandboxing applies when `path` scope is given.

### Testing

- No-double-count invariant for Call/ClassDef-base Name nodes vs. generic reads.
- `read`/`write` kind emission, including the `key=_rank_sort_key`-style regression case and the
  bare-decorator case.
- Declaration-index incremental refresh correctness (added/changed/removed files).
- Deterministic ordering and bounding for `repo.find_definition`.

### SPEC impact

- §10.4: confirm `read`/`write` are now actually emitted by the Python adapter (currently listed
  only as "for example").
- New §11.10 documenting `repo.find_definition`'s contract.

## Track B: Optional semantic + hybrid search

**Scope:** new optional install extra (`onnxruntime` + a lightweight tokenizer), amends SPEC's
"no LLM calls" / `bm25`-only constraints, requires a new ADR. Core server (`dependencies = []`,
BM25-only) is unchanged when the extra is absent — purely additive.

### Constraint reconciliation

`SPEC.md` §3 lists "No LLM calls in v1" as a non-goal and §11.5 locks `repo.search.mode` to
`"bm25"`. This design amends both, scoped narrowly: **local, deterministic-per-machine sentence
embedding inference for retrieval ranking** is carved out from the "no LLM calls" non-goal;
generative/agentic LLM calls remain explicitly out of scope. This is a SPEC-level decision (not
just an ADR overriding `ADR-0009`'s dependency-aversion precedent), confirmed explicitly with the
project owner before this design was approved.

### Components

1. **New optional dependency group** in `pyproject.toml`:
   `[project.optional-dependencies] semantic = ["onnxruntime>=...", "tokenizers>=..."]`. The
   `tokenizers` package (Rust-backed, Apache-2.0) is used instead of the much heavier
   `transformers`. Core `dependencies = []` is untouched.

2. **Model cache** (`repo_mcp/semantic/model_cache.py`): downloads a fixed, pinned, small,
   permissively-licensed sentence-embedding model (e.g. all-MiniLM-L6-v2, Apache-2.0, ONNX,
   ~90MB) from one hardcoded trusted source URL and exact revision, verifies a SHA256 checksum
   pinned in code before the file is ever loaded, and caches it under `data_dir/models/`. Fails
   closed (refuses to load) on checksum mismatch. The source URL is fixed in code, not
   user-configurable, in v1 — this is the supply-chain-sensitive component and gets explicit
   treatment in the ADR.

3. **Embedder** (`repo_mcp/semantic/embedder.py`): loads the cached ONNX model, tokenizes each
   existing 200-line BM25 chunk (deterministically truncated to the model's max token window —
   chunk boundaries are reused as-is, not re-chunked for embedding purposes), runs inference,
   produces a fixed-size float32 vector per chunk. Known v1 limitation, documented rather than
   hidden: embeddings of long chunks only reflect the truncated prefix.

4. **Vector store:** float32 vectors keyed by `chunk_id` under `data_dir/semantic_index/`,
   refreshed incrementally using the same chunk-hash change tracking `IndexManager` already uses
   for BM25 — only new/changed chunks are re-embedded.

5. **Bootstrap/trigger:** no model download or embedding computation happens unless semantic mode
   is actually used. The model downloads lazily on the first `semantic`- or `hybrid`-mode tool
   call. A plain `mode="bm25"` `repo.search` or a normal `repo.refresh_index` never triggers
   network access.

6. **`repo.search` integration:** `mode` gains two new values:
   - `"semantic"` — pure cosine-similarity ranking over chunk vectors.
   - `"hybrid"` — deterministic weighted sum of normalized BM25 score and normalized cosine
     score, with a fixed default weight (0.5 / 0.5) documented in SPEC as part of the contract,
     not left as an implicit implementation detail.
   If `[semantic]` isn't installed, or the model isn't yet cached, requesting `semantic`/`hybrid`
   returns an explicit `isError: true` response with a clear reason — never a silent fallback to
   BM25.

7. **`repo.build_context_bundle` integration:** when semantic is available and requested, the
   hybrid score replaces the existing `search_score` value feeding the bundler's deterministic
   lexicographic ranking key. The rest of the chain
   (`definition_match` → `reference_proximity` → `path_name_relevance` → `search_score` →
   `range_size_penalty` → path/line/query/id tie-breaks) is structurally unchanged — this is a
   substitution at one existing signal slot, not a new ranking dimension.

8. **`repo.status` additions:** `semantic_available` (bool, extra installed) and
   `semantic_model_status` (`"not_installed"` / `"not_downloaded"` / `"ready"`), so a calling AI
   can detect capability before attempting semantic mode.

### Determinism stance

Same-machine repeated runs are reproducible: fixed model weights (checksum-pinned), fixed
tokenization, single deterministic inference path. Cross-machine bit-identical float output is
not guaranteed (consistent with how BM25's own float scores already behave) — the existing
path/line/query/id tie-breaks absorb that jitter the same way they already absorb BM25 scoring
noise. This is documented in the ADR as an accepted characteristic, not a regression against the
"identical across repeated runs" determinism guarantee, which is about same-setup reproducibility.

### Error handling

- Semantic/hybrid mode requested without the extra installed → explicit error, not silent
  fallback.
- Model checksum mismatch → fail closed, explicit error, no partial/unverified model use.
- Embedding inference failure on a given chunk → that chunk is excluded from semantic results
  (logged), does not fail the whole search.

### Testing

- Unit tests use a stub/mock embedder interface — no real model download in CI, consistent with
  the project's existing "no network calls in tests" rule.
- Checksum-mismatch rejection.
- Incremental re-embedding correctness (added/changed/removed chunks).
- Hybrid score formula correctness and determinism.
- Explicit-error behavior when the extra/model isn't available.
- Bundler ranking-chain integration: only the `search_score` slot changes; all other signals are
  asserted unchanged.

### SPEC / ADR impact

- New ADR (e.g. `ADR-0018`) covering: the dependency/precedent override (vs. `ADR-0009`), model
  sourcing and checksum policy, determinism stance, explicit non-goals (no fine-tuning, no remote
  inference, no user-configurable model source in v1).
- SPEC §3: amend "No LLM calls in v1" non-goal to carve out local-inference retrieval embeddings,
  explicitly retaining the prohibition on generative/agentic LLM calls.
- SPEC §11.1 (`repo.status`): document the two new fields.
- SPEC §11.5 (`repo.search`): document `semantic`/`hybrid` modes and the hybrid weight formula.

## Sequencing

Track A has no SPEC non-goal changes and no new dependencies — it can be planned and implemented
immediately. Track B requires the SPEC amendment and new ADR to land first (as documentation/
decision artifacts), then implementation. The two tracks do not share code and can proceed as
separate implementation plans.
