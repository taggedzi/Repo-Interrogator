# Optional Semantic + Hybrid Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution prerequisite:** this plan assumes `docs/superpowers/plans/2026-06-30-reference-conformance-and-find-definition.md` ("Track A") has already landed. Track A and this plan ("Track B") both edit `server.py`, `tools/builtin.py`, `tools/schemas.py`, `SPEC.md`, `README.md`, `docs/AI_INTEGRATION.md`, and `docs/USAGE.md`. Every edit to those shared files below is anchored **symbolically** (by surrounding code/section, not by line number) for exactly this reason — re-locate each anchor in the current file before editing; do not assume the line numbers from the design doc or from Track A still apply.

**Goal:** Add an opt-in semantic embedding layer so `repo.search` and `repo.build_context_bundle` can match on meaning, not just shared vocabulary — closing the demonstrated case where querying `"throttle rate limit"` against code that says "rate limit" differently (or not at all) returns nothing useful from BM25 alone.

**Architecture:** A new `repo_mcp/semantic/` package, active only when the `[semantic]` extra is installed and a cached local ONNX model is present. Core server behavior (BM25-only, zero runtime dependencies) is unchanged when the extra is absent. Embeddings are computed per existing BM25 chunk (reusing chunk boundaries and the existing chunk-hash incremental-refresh signal), stored as a sidecar JSONL vector store, and combined with BM25 via Reciprocal Rank Fusion (RRF) for `mode="hybrid"` — no raw-score normalization, so no SPEC determinism risk from cross-system score scales.

**Tech Stack:** Python 3.11+, `onnxruntime` (ONNX model inference), `tokenizers` (Rust-backed HF tokenizer, not the heavier `transformers` package), stdlib `urllib.request`/`hashlib` for model download+verification. No `numpy` import in this project's own code — vector storage and cosine similarity are pure-Python (dimensionality is 384 floats per chunk; pure-Python dot products are fast enough at this scale and avoid taking an explicit dependency on a library that's otherwise only a transitive dependency of `onnxruntime`).

## Global Constraints

- Core package (`pip install repo-interrogator`) keeps `dependencies = []` — every new dependency in this plan goes under `[project.optional-dependencies] semantic`.
- Plain `mode="bm25"` `repo.search` calls and normal `repo.refresh_index` runs must never trigger a network call or require the `[semantic]` extra to be installed.
- `semantic`/`hybrid` mode requested without the extra installed, or without the model downloaded yet, returns an explicit `isError: true` response — never a silent fallback to BM25.
- Model source is one fixed, pinned URL + exact revision + SHA256 checksum, all hardcoded in source. Not user-configurable in v1. Checksum mismatch → fail closed, refuse to load.
- No network calls in tests (project-wide rule). All tests in this plan use a stub/fake embedder or a local fixture HTTP server — never the real model or real Hugging Face URLs.
- Ruff only (`python -m ruff format .`, `python -m ruff check .`); `python -m mypy src` must pass (strict mode).
- Determinism: same-machine repeated runs must be reproducible. Cross-machine bit-identical float output is not required (same tolerance BM25's own float scoring already has) — RRF's rank-based fusion (not raw-score fusion) keeps the final ordering robust to that jitter; ties still resolve via explicit `path`/`start_line`/`end_line` tie-breaks.

---

### Task 1: `[semantic]` extra, package skeleton, ADR, and SPEC non-goal carve-out

**Files:**
- Modify: `pyproject.toml`
- Create: `src/repo_mcp/semantic/__init__.py`
- Create: `docs/adr/ADR-0018-optional-semantic-search-via-onnx.md`
- Modify: `SPEC.md` (§3 non-goals)

**Interfaces:**
- Consumes: nothing.
- Produces: `repo_mcp.semantic` as an importable package (empty at this point — populated by later tasks). An import of `repo_mcp.semantic.embedder` must raise a clear `ImportError` with an actionable message when `onnxruntime`/`tokenizers` aren't installed, not an opaque stack trace — this is implemented in Task 3.

- [ ] **Step 1: Add the optional dependency group**

In `pyproject.toml`, find the `[project.optional-dependencies]` table (currently containing `dev` and `release` groups) and add a new `semantic` group:

```toml
semantic = [
  "onnxruntime>=1.18",
  "tokenizers>=0.19",
]
```

Leave `dependencies = []` untouched — this is purely additive.

- [ ] **Step 2: Create the package skeleton**

Create `src/repo_mcp/semantic/__init__.py`:

```python
"""Optional local semantic embedding support.

Everything in this package is inert unless the `semantic` extra
(onnxruntime + tokenizers) is installed and a cached model is present.
Importing this package itself never requires the extra; importing
`repo_mcp.semantic.embedder` does, and raises a clear ImportError if it's
missing.
"""

from __future__ import annotations
```

- [ ] **Step 3: Write the new ADR**

Create `docs/adr/ADR-0018-optional-semantic-search-via-onnx.md`:

```markdown
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
```

- [ ] **Step 4: Amend SPEC.md's non-goals**

In `SPEC.md`, find the `## 3. Non-goals` section (the bullet list including `* No LLM calls in v1`). Change that bullet from:

```
* No LLM calls in v1
```

to:

```
* No LLM calls in v1 (generative or agentic). Local, deterministic-per-machine
  sentence-embedding inference for retrieval ranking is a distinct, narrowly
  scoped, opt-in capability — see §11.5 and §11.7 and `ADR-0018`.
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/repo_mcp/semantic/__init__.py docs/adr/ADR-0018-optional-semantic-search-via-onnx.md SPEC.md
git commit -m "$(cat <<'EOF'
docs: add ADR-0018 and SPEC carve-out for optional semantic search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Model cache (download once, checksum-verify, cache locally)

**Files:**
- Create: `src/repo_mcp/semantic/model_cache.py`
- Test: `tests/unit/semantic/test_model_cache.py` (new — create `tests/unit/semantic/__init__.py` too if the directory needs it; check whether `tests/unit/` subdirectories elsewhere have `__init__.py` files and match that convention)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ModelCache` class in `repo_mcp.semantic.model_cache` with `ensure_model(data_dir: Path) -> ModelFiles` (downloads+verifies+caches if needed, returns paths) and a `ModelChecksumError` exception. `ModelFiles` is a frozen dataclass with `model_path: Path` and `tokenizer_path: Path`, consumed by Task 3's embedder.

- [ ] **Step 1: Write the failing tests**

First check whether other `tests/unit/<subpackage>/` directories have an `__init__.py` (run `ls tests/unit/adapters/` — if `__init__.py` is absent there, don't add one for `tests/unit/semantic/` either; pytest's rootdir-relative discovery doesn't require it). Create `tests/unit/semantic/test_model_cache.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from repo_mcp.semantic.model_cache import (
    ModelCache,
    ModelChecksumError,
    ModelSpec,
)


def _write_fake_source(tmp_path: Path, content: bytes) -> Path:
    source = tmp_path / "source" / "fake_model.onnx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    return source


def test_ensure_model_downloads_and_caches_on_first_use(tmp_path: Path) -> None:
    model_bytes = b"fake-onnx-model-bytes"
    tokenizer_bytes = b"fake-tokenizer-json-bytes"
    model_source = _write_fake_source(tmp_path, model_bytes)
    tokenizer_source = model_source.parent / "fake_tokenizer.json"
    tokenizer_source.write_bytes(tokenizer_bytes)

    spec = ModelSpec(
        model_url=model_source.as_uri(),
        model_sha256=hashlib.sha256(model_bytes).hexdigest(),
        tokenizer_url=tokenizer_source.as_uri(),
        tokenizer_sha256=hashlib.sha256(tokenizer_bytes).hexdigest(),
        cache_subdir="fake-model-v1",
    )
    data_dir = tmp_path / "data"
    cache = ModelCache(spec=spec)

    files = cache.ensure_model(data_dir)

    assert files.model_path.read_bytes() == model_bytes
    assert files.tokenizer_path.read_bytes() == tokenizer_bytes
    assert files.model_path.is_relative_to(data_dir)


def test_ensure_model_reuses_cache_without_redownloading(tmp_path: Path, monkeypatch) -> None:
    model_bytes = b"fake-onnx-model-bytes"
    tokenizer_bytes = b"fake-tokenizer-json-bytes"
    model_source = _write_fake_source(tmp_path, model_bytes)
    tokenizer_source = model_source.parent / "fake_tokenizer.json"
    tokenizer_source.write_bytes(tokenizer_bytes)

    spec = ModelSpec(
        model_url=model_source.as_uri(),
        model_sha256=hashlib.sha256(model_bytes).hexdigest(),
        tokenizer_url=tokenizer_source.as_uri(),
        tokenizer_sha256=hashlib.sha256(tokenizer_bytes).hexdigest(),
        cache_subdir="fake-model-v1",
    )
    data_dir = tmp_path / "data"
    cache = ModelCache(spec=spec)
    cache.ensure_model(data_dir)

    download_calls = 0
    original_urlretrieve = cache._download

    def counting_download(url: str, destination: Path) -> None:
        nonlocal download_calls
        download_calls += 1
        original_urlretrieve(url, destination)

    monkeypatch.setattr(cache, "_download", counting_download)
    cache.ensure_model(data_dir)

    assert download_calls == 0


def test_ensure_model_rejects_checksum_mismatch(tmp_path: Path) -> None:
    model_bytes = b"fake-onnx-model-bytes"
    tokenizer_bytes = b"fake-tokenizer-json-bytes"
    model_source = _write_fake_source(tmp_path, model_bytes)
    tokenizer_source = model_source.parent / "fake_tokenizer.json"
    tokenizer_source.write_bytes(tokenizer_bytes)

    spec = ModelSpec(
        model_url=model_source.as_uri(),
        model_sha256="0" * 64,
        tokenizer_url=tokenizer_source.as_uri(),
        tokenizer_sha256=hashlib.sha256(tokenizer_bytes).hexdigest(),
        cache_subdir="fake-model-v1",
    )
    data_dir = tmp_path / "data"
    cache = ModelCache(spec=spec)

    with pytest.raises(ModelChecksumError):
        cache.ensure_model(data_dir)

    cached_model = data_dir / "models" / "fake-model-v1" / "model.onnx"
    assert not cached_model.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/semantic/test_model_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repo_mcp.semantic.model_cache'`.

- [ ] **Step 3: Implement `model_cache.py`**

Create `src/repo_mcp/semantic/model_cache.py`:

```python
"""Download-once, checksum-verified local cache for the semantic embedding model."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_SPEC_CACHE_SUBDIR = "all-minilm-l6-v2-quantized"


class ModelChecksumError(Exception):
    """Raised when a downloaded model/tokenizer file fails checksum verification."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Pinned source location and expected checksums for the embedding model."""

    model_url: str
    model_sha256: str
    tokenizer_url: str
    tokenizer_sha256: str
    cache_subdir: str


@dataclass(frozen=True, slots=True)
class ModelFiles:
    """Resolved local paths to a verified, cached model and tokenizer."""

    model_path: Path
    tokenizer_path: Path


class ModelCache:
    """Ensures a pinned model/tokenizer pair is downloaded, verified, and cached."""

    def __init__(self, spec: ModelSpec) -> None:
        self._spec = spec

    def ensure_model(self, data_dir: Path) -> ModelFiles:
        """Return cached, verified model files, downloading them if not already cached."""
        cache_dir = data_dir / "models" / self._spec.cache_subdir
        model_path = cache_dir / "model.onnx"
        tokenizer_path = cache_dir / "tokenizer.json"

        if model_path.exists() and tokenizer_path.exists():
            return ModelFiles(model_path=model_path, tokenizer_path=tokenizer_path)

        cache_dir.mkdir(parents=True, exist_ok=True)
        self._fetch_and_verify(
            url=self._spec.model_url,
            expected_sha256=self._spec.model_sha256,
            destination=model_path,
        )
        self._fetch_and_verify(
            url=self._spec.tokenizer_url,
            expected_sha256=self._spec.tokenizer_sha256,
            destination=tokenizer_path,
        )
        return ModelFiles(model_path=model_path, tokenizer_path=tokenizer_path)

    def _fetch_and_verify(self, *, url: str, expected_sha256: str, destination: Path) -> None:
        with tempfile.TemporaryDirectory(dir=destination.parent) as tmp_dir:
            tmp_path = Path(tmp_dir) / destination.name
            self._download(url, tmp_path)
            actual_sha256 = _sha256_of_file(tmp_path)
            if actual_sha256 != expected_sha256:
                raise ModelChecksumError(
                    f"Checksum mismatch for {url}: expected {expected_sha256}, "
                    f"got {actual_sha256}. Refusing to cache an unverified file."
                )
            shutil.move(str(tmp_path), str(destination))

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        with urllib.request.urlopen(url) as response, destination.open("wb") as handle:  # noqa: S310
            shutil.copyfileobj(response, handle)


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

Note on the `# noqa: S310` comment: `urllib.request.urlopen` with a variable URL trips Ruff's `S310` (Bandit) audit-URL-open-for-permitted-schemes check. The URL here is always one of the two hardcoded, pinned URLs in the production `ModelSpec` constant added in Step 4 — never user input — so the suppression is justified the same way `ADR-0018` already documents the source as fixed and non-configurable. If `python -m ruff check .` flags this differently than expected, adjust the noqa code to match ruff's actual rule id rather than removing the safety property it documents.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/semantic/test_model_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Pin the real model spec as a module-level constant**

This is the one step in this plan that depends on a fact only obtainable by actually visiting the model source — do this once, by hand, before continuing:

1. Visit `https://huggingface.co/Xenova/all-MiniLM-L6-v2/tree/main/onnx` and note the exact commit hash for `main` (Hugging Face shows it in the file browser, or resolve it via `git ls-remote https://huggingface.co/Xenova/all-MiniLM-L6-v2 main`). Pin that 40-character SHA — never use a moving `main` reference in the shipped constant.
2. Download `onnx/model_quantized.onnx` and `tokenizer.json` from that exact commit once, compute `sha256sum` on each.
3. Add to `src/repo_mcp/semantic/model_cache.py`, after the `ModelCache` class:

```python
DEFAULT_MODEL_SPEC = ModelSpec(
    model_url=(
        "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/"
        "<PINNED_COMMIT_SHA>/onnx/model_quantized.onnx"
    ),
    model_sha256="<PINNED_MODEL_SHA256>",
    tokenizer_url=(
        "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/"
        "<PINNED_COMMIT_SHA>/tokenizer.json"
    ),
    tokenizer_sha256="<PINNED_TOKENIZER_SHA256>",
    cache_subdir=DEFAULT_MODEL_SPEC_CACHE_SUBDIR,
)
```

Replace `<PINNED_COMMIT_SHA>`, `<PINNED_MODEL_SHA256>`, and `<PINNED_TOKENIZER_SHA256>` with the real values from sub-steps 1-2. Add a unit test asserting `DEFAULT_MODEL_SPEC.model_sha256` and `.tokenizer_sha256` are each 64 hex characters (`len(value) == 64` and `int(value, 16)` doesn't raise) as a basic sanity guard against an unfilled placeholder shipping.

- [ ] **Step 6: Commit**

```bash
git add src/repo_mcp/semantic/model_cache.py tests/unit/semantic/
git commit -m "$(cat <<'EOF'
feat: add checksum-verified local model cache for semantic search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Embedder (tokenize, ONNX inference, mean-pool, normalize)

**Files:**
- Create: `src/repo_mcp/semantic/embedder.py`
- Test: `tests/unit/semantic/test_embedder.py` (new)

**Interfaces:**
- Consumes: `ModelFiles` (Task 2).
- Produces: `Embedder` class with `embed(text: str) -> tuple[float, ...]` (fixed-length, L2-normalized vector) and `is_semantic_extra_installed() -> bool` module-level function, both consumed by Task 4 (vector store population) and Task 5 (query-time embedding).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/semantic/test_embedder.py`. These tests stub the ONNX/tokenizer layer entirely — no real model, no `[semantic]` extra required to run this test file:

```python
from __future__ import annotations

import math

from repo_mcp.semantic.embedder import Embedder, _mean_pool_and_normalize


def test_mean_pool_and_normalize_produces_unit_length_vector() -> None:
    token_embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    attention_mask = [1, 1, 1]

    pooled = _mean_pool_and_normalize(token_embeddings, attention_mask)

    length = math.sqrt(sum(value * value for value in pooled))
    assert math.isclose(length, 1.0, rel_tol=1e-6)


def test_mean_pool_and_normalize_ignores_padding_tokens() -> None:
    token_embeddings = [
        [2.0, 0.0],
        [0.0, 2.0],
        [100.0, 100.0],
    ]
    attention_mask = [1, 1, 0]

    pooled = _mean_pool_and_normalize(token_embeddings, attention_mask)

    expected_raw = [1.0, 1.0]
    expected_length = math.sqrt(sum(value * value for value in expected_raw))
    expected = [value / expected_length for value in expected_raw]
    assert all(math.isclose(a, b, rel_tol=1e-6) for a, b in zip(pooled, expected, strict=True))


def test_embedder_embed_delegates_to_session_and_pools(monkeypatch) -> None:
    class _FakeEncoding:
        ids = [101, 2054, 102]
        attention_mask = [1, 1, 1]

    class _FakeTokenizer:
        @staticmethod
        def encode(text: str) -> _FakeEncoding:
            assert text == "hello world"
            return _FakeEncoding()

    class _FakeSession:
        def get_inputs(self):
            class _Input:
                def __init__(self, name: str) -> None:
                    self.name = name

            return [_Input("input_ids"), _Input("attention_mask"), _Input("token_type_ids")]

        def run(self, output_names, inputs):
            assert inputs["input_ids"][0] == [101, 2054, 102]
            token_embeddings = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
            return [[token_embeddings]]

    embedder = Embedder.__new__(Embedder)
    embedder._tokenizer = _FakeTokenizer()
    embedder._session = _FakeSession()
    embedder._max_tokens = 256

    vector = embedder.embed("hello world")

    assert len(vector) == 2
    length = math.sqrt(sum(value * value for value in vector))
    assert math.isclose(length, 1.0, rel_tol=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/semantic/test_embedder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repo_mcp.semantic.embedder'`.

- [ ] **Step 3: Implement `embedder.py`**

Create `src/repo_mcp/semantic/embedder.py`:

```python
"""ONNX-backed sentence embedding for semantic search (requires the `semantic` extra)."""

from __future__ import annotations

import math
from pathlib import Path

from repo_mcp.semantic.model_cache import ModelFiles

try:
    import onnxruntime as ort
    from tokenizers import Tokenizer

    _SEMANTIC_EXTRA_INSTALLED = True
except ImportError:  # pragma: no cover - exercised only when the extra is absent
    _SEMANTIC_EXTRA_INSTALLED = False


def is_semantic_extra_installed() -> bool:
    """Return True when onnxruntime and tokenizers are both importable."""
    return _SEMANTIC_EXTRA_INSTALLED


class SemanticExtraNotInstalledError(ImportError):
    """Raised when semantic functionality is used without the `semantic` extra installed."""


class Embedder:
    """Computes fixed-size, L2-normalized sentence embeddings for chunk text."""

    def __init__(self, files: ModelFiles, *, max_tokens: int = 256) -> None:
        if not _SEMANTIC_EXTRA_INSTALLED:
            raise SemanticExtraNotInstalledError(
                "The 'semantic' extra is not installed. Install it with "
                "`pip install repo-interrogator[semantic]` to use semantic/hybrid search."
            )
        self._tokenizer = Tokenizer.from_file(str(files.tokenizer_path))
        self._tokenizer.enable_truncation(max_length=max_tokens)
        self._session = ort.InferenceSession(
            str(files.model_path), providers=["CPUExecutionProvider"]
        )
        self._max_tokens = max_tokens

    def embed(self, text: str) -> tuple[float, ...]:
        """Return a deterministic, L2-normalized embedding vector for text."""
        encoding = self._tokenizer.encode(text)
        input_ids = [encoding.ids]
        attention_mask = [encoding.attention_mask]
        input_names = {item.name for item in self._session.get_inputs()}
        feed: dict[str, list[list[int]]] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in input_names:
            feed["token_type_ids"] = [[0] * len(encoding.ids)]
        outputs = self._session.run(None, feed)
        token_embeddings = outputs[0][0]
        pooled = _mean_pool_and_normalize(token_embeddings, encoding.attention_mask)
        return tuple(pooled)


def _mean_pool_and_normalize(
    token_embeddings: list[list[float]],
    attention_mask: list[int],
) -> list[float]:
    """Mean-pool token embeddings over non-padding positions, then L2-normalize."""
    dim = len(token_embeddings[0])
    summed = [0.0] * dim
    count = 0
    for embedding, mask in zip(token_embeddings, attention_mask, strict=True):
        if mask == 0:
            continue
        for index in range(dim):
            summed[index] += embedding[index]
        count += 1
    if count == 0:
        return [0.0] * dim
    pooled = [value / count for value in summed]
    length = math.sqrt(sum(value * value for value in pooled))
    if length == 0.0:
        return pooled
    return [value / length for value in pooled]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/semantic/test_embedder.py -v`
Expected: PASS. These tests never import the real `onnxruntime`/`tokenizers` packages (they bypass `Embedder.__init__` via `__new__` and stub `_tokenizer`/`_session` directly, and the pooling tests call the pure-Python `_mean_pool_and_normalize` helper in isolation), so this file passes in CI without the `semantic` extra installed.

- [ ] **Step 5: Add an extra-not-installed integration check**

Add to `tests/unit/semantic/test_embedder.py`:

```python
def test_is_semantic_extra_installed_reflects_import_availability() -> None:
    from repo_mcp.semantic import embedder

    assert embedder.is_semantic_extra_installed() in (True, False)
```

Run: `python -m pytest tests/unit/semantic/test_embedder.py -v`
Expected: PASS (this just exercises whatever is actually installed in the current environment without asserting a specific value, since CI may or may not have the extra installed).

- [ ] **Step 6: Commit**

```bash
git add src/repo_mcp/semantic/embedder.py tests/unit/semantic/test_embedder.py
git commit -m "$(cat <<'EOF'
feat: add ONNX-backed embedder for semantic search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Vector store with incremental refresh tied to existing chunk hashes

**Files:**
- Create: `src/repo_mcp/semantic/vector_store.py`
- Test: `tests/unit/semantic/test_vector_store.py` (new)

**Interfaces:**
- Consumes: `ChunkRecord` shape (`path`, `start_line`, `end_line`, `chunk_id`) from `repo_mcp.index.models` (existing — `chunk_id` is already a content hash per `src/repo_mcp/index/chunking.py:54-65`, so unchanged chunk text always produces the same `chunk_id`, which is exactly what incremental refresh needs); `Embedder.embed` (Task 3).
- Produces: `VectorStore` class with `refresh(chunks: list[ChunkRecord], read_chunk_text: Callable[[ChunkRecord], str], embedder: Embedder) -> VectorRefreshResult` and `load_vectors() -> dict[str, tuple[float, ...]]` (chunk_id → vector), consumed by Task 5's search-fusion layer.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/semantic/test_vector_store.py`:

```python
from __future__ import annotations

from pathlib import Path

from repo_mcp.index.models import ChunkRecord
from repo_mcp.semantic.vector_store import VectorStore


class _FakeEmbedder:
    def __init__(self) -> None:
        self.embed_calls: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.embed_calls.append(text)
        return (float(len(text)), 0.0, 0.0)


def _chunk(chunk_id: str, path: str = "a.py") -> ChunkRecord:
    return ChunkRecord(path=path, start_line=1, end_line=1, chunk_id=chunk_id)


def test_vector_store_refresh_embeds_new_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    chunks = [_chunk("id-1"), _chunk("id-2")]

    result = store.refresh(chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder)

    assert result.embedded == 2
    assert result.reused == 0
    assert result.removed == 0
    assert sorted(embedder.embed_calls) == ["text-id-1", "text-id-2"]

    vectors = store.load_vectors()
    assert set(vectors.keys()) == {"id-1", "id-2"}


def test_vector_store_refresh_reuses_unchanged_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    chunks = [_chunk("id-1")]
    store.refresh(chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder)

    embedder.embed_calls.clear()
    result = store.refresh(chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder)

    assert result.embedded == 0
    assert result.reused == 1
    assert embedder.embed_calls == []


def test_vector_store_refresh_removes_stale_chunks(tmp_path: Path) -> None:
    store = VectorStore(data_dir=tmp_path)
    embedder = _FakeEmbedder()
    store.refresh(
        [_chunk("id-1"), _chunk("id-2")],
        read_chunk_text=lambda c: f"text-{c.chunk_id}",
        embedder=embedder,
    )

    result = store.refresh(
        [_chunk("id-1")],
        read_chunk_text=lambda c: f"text-{c.chunk_id}",
        embedder=embedder,
    )

    assert result.removed == 1
    assert set(store.load_vectors().keys()) == {"id-1"}


def test_vector_store_refresh_skips_chunk_on_embedding_failure(tmp_path: Path) -> None:
    class _FailingEmbedder:
        def embed(self, text: str) -> tuple[float, ...]:
            if text == "text-id-bad":
                raise RuntimeError("inference failed")
            return (1.0, 0.0, 0.0)

    store = VectorStore(data_dir=tmp_path)
    chunks = [_chunk("id-good"), _chunk("id-bad")]

    result = store.refresh(
        chunks, read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=_FailingEmbedder()
    )

    assert result.embedded == 1
    assert result.failed == 1
    assert set(store.load_vectors().keys()) == {"id-good"}


def test_vector_store_persists_across_instances(tmp_path: Path) -> None:
    embedder = _FakeEmbedder()
    VectorStore(data_dir=tmp_path).refresh(
        [_chunk("id-1")], read_chunk_text=lambda c: f"text-{c.chunk_id}", embedder=embedder
    )

    reloaded = VectorStore(data_dir=tmp_path)
    vectors = reloaded.load_vectors()

    assert vectors["id-1"] == (float(len("text-id-1")), 0.0, 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/semantic/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repo_mcp.semantic.vector_store'`.

- [ ] **Step 3: Implement `vector_store.py`**

Create `src/repo_mcp/semantic/vector_store.py`:

```python
"""Sidecar vector store for chunk embeddings, incrementally refreshed by chunk_id."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from repo_mcp.index.models import ChunkRecord


class _EmbedderProtocol(Protocol):
    def embed(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True, slots=True)
class VectorRefreshResult:
    embedded: int
    reused: int
    removed: int
    failed: int


class VectorStore:
    """Persists chunk_id -> embedding vector, keyed off the existing content-hash chunk_id."""

    def __init__(self, data_dir: Path) -> None:
        self._vectors_path = data_dir / "semantic_index" / "vectors.jsonl"

    def refresh(
        self,
        chunks: list[ChunkRecord],
        *,
        read_chunk_text: Callable[[ChunkRecord], str],
        embedder: _EmbedderProtocol,
    ) -> VectorRefreshResult:
        """Embed any chunk_id not already stored, drop chunk_ids no longer present."""
        existing = self.load_vectors()
        current_ids = {chunk.chunk_id for chunk in chunks}
        embedded = 0
        reused = 0
        failed = 0
        updated: dict[str, tuple[float, ...]] = {}
        for chunk in sorted(chunks, key=lambda item: item.chunk_id):
            if chunk.chunk_id in existing:
                updated[chunk.chunk_id] = existing[chunk.chunk_id]
                reused += 1
                continue
            try:
                vector = embedder.embed(read_chunk_text(chunk))
            except Exception:
                # A single chunk's embedding failure (e.g. a transient ONNX
                # runtime error) must not abort the whole refresh or take down
                # semantic search for every other chunk. The chunk is simply
                # left out of the vector store and re-attempted on the next
                # refresh, since it won't be in `existing` next time either.
                failed += 1
                continue
            updated[chunk.chunk_id] = vector
            embedded += 1
        removed = len(set(existing.keys()) - current_ids)
        self._write_vectors(updated)
        return VectorRefreshResult(embedded=embedded, reused=reused, removed=removed, failed=failed)

    def load_vectors(self) -> dict[str, tuple[float, ...]]:
        """Return all currently stored chunk_id -> vector pairs."""
        if not self._vectors_path.exists():
            return {}
        vectors: dict[str, tuple[float, ...]] = {}
        with self._vectors_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                chunk_id = obj.get("chunk_id")
                vector = obj.get("vector")
                if not isinstance(chunk_id, str) or not isinstance(vector, list):
                    continue
                vectors[chunk_id] = tuple(float(value) for value in vector)
        return vectors

    def _write_vectors(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._vectors_path.with_suffix(".jsonl.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for chunk_id in sorted(vectors.keys()):
                row = {"chunk_id": chunk_id, "vector": list(vectors[chunk_id])}
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")
        tmp_path.replace(self._vectors_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/semantic/test_vector_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/repo_mcp/semantic/vector_store.py tests/unit/semantic/test_vector_store.py
git commit -m "$(cat <<'EOF'
feat: add incrementally-refreshed vector store for chunk embeddings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Cosine search + Reciprocal Rank Fusion

**Files:**
- Create: `src/repo_mcp/semantic/fusion.py`
- Test: `tests/unit/semantic/test_fusion.py` (new)

**Interfaces:**
- Consumes: `dict[str, tuple[float, ...]]` vectors (Task 4), `Embedder.embed` (Task 3, for the query vector), and BM25 hit dicts in the existing `SearchHit`-shaped form (`path`, `start_line`, `end_line`, `snippet`, `score`, `matched_terms` — see `src/repo_mcp/index/search.py:25-34`).
- Produces: `semantic_search(query_vector, chunk_vectors, chunk_metadata, top_k) -> list[dict]` and `reciprocal_rank_fusion(bm25_hits, semantic_hits, top_k, k=60) -> list[dict]` in `repo_mcp.semantic.fusion`, both consumed by Task 6's `IndexManager` wiring.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/semantic/test_fusion.py`:

```python
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
        {"path": "shared.py", "start_line": 1, "end_line": 5, "score": 10.0, "snippet": "", "matched_terms": ["x"]},
        {"path": "bm25_only.py", "start_line": 1, "end_line": 5, "score": 5.0, "snippet": "", "matched_terms": ["x"]},
    ]
    semantic_hits = [
        {"path": "shared.py", "start_line": 1, "end_line": 5, "score": 0.9, "snippet": "", "matched_terms": []},
        {"path": "semantic_only.py", "start_line": 1, "end_line": 5, "score": 0.8, "snippet": "", "matched_terms": []},
    ]

    fused = reciprocal_rank_fusion(bm25_hits, semantic_hits, top_k=10)

    assert fused[0]["path"] == "shared.py"
    assert {hit["path"] for hit in fused} == {"shared.py", "bm25_only.py", "semantic_only.py"}


def test_reciprocal_rank_fusion_respects_top_k() -> None:
    bm25_hits = [
        {"path": f"f{i}.py", "start_line": 1, "end_line": 5, "score": float(10 - i), "snippet": "", "matched_terms": []}
        for i in range(5)
    ]
    fused = reciprocal_rank_fusion(bm25_hits, [], top_k=2)
    assert len(fused) == 2


def test_reciprocal_rank_fusion_is_deterministic() -> None:
    bm25_hits = [
        {"path": "a.py", "start_line": 1, "end_line": 5, "score": 1.0, "snippet": "", "matched_terms": []},
        {"path": "b.py", "start_line": 1, "end_line": 5, "score": 1.0, "snippet": "", "matched_terms": []},
    ]
    first = reciprocal_rank_fusion(bm25_hits, [], top_k=10)
    second = reciprocal_rank_fusion(bm25_hits, [], top_k=10)
    assert first == second
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/semantic/test_fusion.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repo_mcp.semantic.fusion'`.

- [ ] **Step 3: Implement `fusion.py`**

Create `src/repo_mcp/semantic/fusion.py`:

```python
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
                    set(existing.get("matched_terms", []) or [])  # type: ignore[arg-type]
                    | set(hit.get("matched_terms", []) or [])  # type: ignore[arg-type]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/semantic/test_fusion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/repo_mcp/semantic/fusion.py tests/unit/semantic/test_fusion.py
git commit -m "$(cat <<'EOF'
feat: add cosine semantic search and RRF hybrid fusion

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Wire `mode="semantic"`/`"hybrid"` into `repo.search`, and `semantic_*` fields into `repo.status`

**Files:**
- Modify: `src/repo_mcp/index/manager.py` (symbolic anchor: the `search` method and `__init__`)
- Modify: `src/repo_mcp/tools/schemas.py` (symbolic anchor: the `"repo.search"` and `"repo.status"` entries)
- Modify: `src/repo_mcp/tools/builtin.py` (symbolic anchor: `_search_handler` and `_status_handler`)
- Modify: `src/repo_mcp/server.py` (symbolic anchor: `StdioServer.__init__` and wherever `IndexManager` is constructed)
- Test: `tests/integration/test_repo_search_semantic_modes.py` (new)

**Interfaces:**
- Consumes: `VectorStore.load_vectors` (Task 4), `Embedder.embed` and `is_semantic_extra_installed` (Task 3), `semantic_search`/`reciprocal_rank_fusion` (Task 5).
- Produces: `repo.search` accepts `mode` values `"bm25"` (existing default), `"semantic"`, `"hybrid"`. `repo.status` result gains `semantic_available: bool` and `semantic_model_status: "not_installed" | "not_downloaded" | "ready"`.

**Design note (read before writing tests):** gating must be network-safe in *every* CI environment regardless of whether the `[semantic]` extra happens to be installed there. The rule implemented in Step 3 is: `search(mode="semantic"|"hybrid")` raises `SemanticNotAvailableError` **only** when `is_semantic_extra_installed()` is `False` — that's the one case that truly cannot proceed. If the extra *is* installed, the first call transparently triggers the model download (per the design's "lazy bootstrap" requirement) rather than erroring on "not yet cached." Because of this, every test below that wants the not-available error path must **monkeypatch `is_semantic_extra_installed` to `False` directly**, never rely on it actually being absent from the test environment — otherwise the test would silently attempt a real download over the network on any machine that happens to have the extra installed, violating the project's no-network-in-tests rule.

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_repo_search_semantic_modes.py`:

```python
from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.index import manager as manager_module
from repo_mcp.server import create_server


def test_repo_search_semantic_mode_without_extra_returns_explicit_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)

    response = call_tool(
        server, "req-sem-1", "repo.search", {"query": "f", "mode": "semantic", "top_k": 5}
    )

    assert is_tool_error(response)


def test_repo_search_hybrid_mode_without_extra_returns_explicit_error(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)

    response = call_tool(
        server, "req-sem-2", "repo.search", {"query": "f", "mode": "hybrid", "top_k": 5}
    )

    assert is_tool_error(response)


def test_repo_status_reports_semantic_not_installed_when_extra_absent(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: False)
    server = create_server(repo_root=str(tmp_path))

    result = extract_result(call_tool(server, "req-status-1", "repo.status", {}))

    assert result["semantic_available"] is False
    assert result["semantic_model_status"] == "not_installed"


def test_repo_search_hybrid_mode_fuses_results_when_semantic_available(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    monkeypatch.setattr(manager_module, "is_semantic_extra_installed", lambda: True)
    fake_semantic_hits = [
        {
            "path": "a.py",
            "start_line": 1,
            "end_line": 2,
            "snippet": "def f():",
            "score": 0.9,
            "matched_terms": [],
        }
    ]
    monkeypatch.setattr(
        manager_module.IndexManager,
        "_semantic_search_hits",
        lambda self, *, query, top_k, filtered: fake_semantic_hits,
    )

    response = call_tool(
        server, "req-sem-3", "repo.search", {"query": "f", "mode": "hybrid", "top_k": 5}
    )

    assert not is_tool_error(response)
    result = extract_result(response)
    assert "hits" in result
    assert any(hit["path"] == "a.py" for hit in result["hits"])
```

This `_semantic_search_hits` monkeypatch is the key to keeping this test network-free: it replaces the *whole* method (which would otherwise call `refresh_semantic_index()` → `_get_embedder()` → a real model download) with a canned result, so nothing below `IndexManager.search` actually touches `onnxruntime`, `tokenizers`, or the network — this test passes identically whether or not the `[semantic]` extra happens to be installed in the environment running it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_repo_search_semantic_modes.py -v`
Expected: FAIL — `mode="semantic"`/`"hybrid"` currently raise `INVALID_PARAMS` ("mode must be 'bm25' in v1") rather than the new semantic-specific error, `repo.status` has no `semantic_available` key, and `is_semantic_extra_installed`/`_semantic_search_hits` don't exist as importable/patchable targets yet.

- [ ] **Step 3: Extend `IndexManager` with semantic-aware search**

In `src/repo_mcp/index/manager.py`, locate the `__init__` method (symbolic anchor: where `self._search_docs_cache_marker` etc. are initialized) and add semantic-related state:

```python
        self._semantic_model_cache: ModelCache | None = None
        self._semantic_embedder: Embedder | None = None
```

Add the import at the top of the file (alongside the existing `from repo_mcp.index.search import SearchDocument, bm25_search` line):

```python
from repo_mcp.semantic.embedder import Embedder, is_semantic_extra_installed
from repo_mcp.semantic.fusion import reciprocal_rank_fusion, semantic_search
from repo_mcp.semantic.model_cache import DEFAULT_MODEL_SPEC, ModelCache, ModelChecksumError
from repo_mcp.semantic.vector_store import VectorStore
```

Note: this import is unconditional (`repo_mcp.semantic.model_cache`/`vector_store`/`fusion` have no third-party dependencies themselves — only `repo_mcp.semantic.embedder` conditionally imports `onnxruntime`/`tokenizers`, and it already degrades to `is_semantic_extra_installed() == False` rather than raising at import time). This keeps `IndexManager` importable with zero extra dependencies.

Locate the existing `search` method (symbolic anchor: `def search(self, query: str, top_k: int, file_glob: str | None = None, path_prefix: str | None = None) -> list[dict[str, object]]:`). Replace it with:

```python
    def search(
        self,
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
        mode: str = "bm25",
    ) -> list[dict[str, object]]:
        """Run deterministic search over indexed chunks in the requested mode."""
        if top_k < 1:
            return []
        filtered = self._load_filtered_search_documents(
            file_glob=file_glob,
            path_prefix=path_prefix,
        )
        if not filtered:
            return []
        if mode == "bm25":
            return bm25_search(documents=filtered, query=query, top_k=top_k)
        if mode in ("semantic", "hybrid"):
            if not is_semantic_extra_installed():
                raise SemanticNotAvailableError(
                    "Semantic/hybrid search requires the 'semantic' extra. "
                    "Install it with `pip install repo-interrogator[semantic]`."
                )
            try:
                semantic_hits = self._semantic_search_hits(
                    query=query, top_k=top_k, filtered=filtered
                )
            except ModelChecksumError as error:
                raise SemanticNotAvailableError(
                    f"Semantic model download failed checksum verification: {error}"
                ) from error
            if mode == "semantic":
                return semantic_hits
            bm25_hits = bm25_search(documents=filtered, query=query, top_k=top_k)
            return reciprocal_rank_fusion(bm25_hits, semantic_hits, top_k=top_k)
        raise ValueError(f"Unsupported search mode: {mode}")

    def semantic_status(self) -> tuple[bool, str]:
        """Return (semantic_available, semantic_model_status) for repo.status.

        This is purely informational (used by repo.status) and is NOT used to
        gate repo.search itself: the first semantic/hybrid search call
        transparently triggers the one-time model download (see
        _semantic_search_hits -> refresh_semantic_index -> _get_embedder),
        rather than erroring just because the model isn't cached yet. Only a
        missing `semantic` extra is a hard block on repo.search (see the
        `search` method above).
        """
        if not is_semantic_extra_installed():
            return False, "not_installed"
        model_path, tokenizer_path = self._semantic_model_paths()
        if not model_path.exists() or not tokenizer_path.exists():
            return True, "not_downloaded"
        return True, "ready"

    def _semantic_model_paths(self) -> tuple[Path, Path]:
        cache_dir = self._data_dir / "models" / DEFAULT_MODEL_SPEC.cache_subdir
        return cache_dir / "model.onnx", cache_dir / "tokenizer.json"

    def _get_embedder(self) -> Embedder:
        if self._semantic_embedder is None:
            if self._semantic_model_cache is None:
                self._semantic_model_cache = ModelCache(spec=DEFAULT_MODEL_SPEC)
            files = self._semantic_model_cache.ensure_model(self._data_dir)
            self._semantic_embedder = Embedder(files)
        return self._semantic_embedder

    def _embed_query(self, query: str) -> tuple[float, ...]:
        return self._get_embedder().embed(query)

    def _load_semantic_vectors(self) -> dict[str, tuple[float, ...]]:
        return VectorStore(data_dir=self._data_dir).load_vectors()

    def _semantic_chunk_metadata(self) -> dict[str, dict[str, object]]:
        metadata: dict[str, dict[str, object]] = {}
        for chunk in self._load_chunks():
            metadata[chunk.chunk_id] = {
                "path": chunk.path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "snippet": "",
            }
        return metadata

    def _semantic_search_hits(
        self, *, query: str, top_k: int, filtered: list[SearchDocument]
    ) -> list[dict[str, object]]:
        allowed_paths = {doc.path for doc in filtered}
        all_vectors = self._load_semantic_vectors()
        all_metadata = self._semantic_chunk_metadata()
        scoped_vectors = {
            chunk_id: vector
            for chunk_id, vector in all_vectors.items()
            if all_metadata.get(chunk_id, {}).get("path") in allowed_paths
        }
        query_vector = self._embed_query(query)
        return semantic_search(
            query_vector=query_vector,
            chunk_vectors=scoped_vectors,
            chunk_metadata=all_metadata,
            top_k=top_k,
        )

    def refresh_semantic_index(self) -> dict[str, object]:
        """Compute/refresh embeddings for all current chunks. Call explicitly, not from refresh()."""
        embedder = self._get_embedder()
        chunks = self._load_chunks()
        store = VectorStore(data_dir=self._data_dir)

        def _read_chunk_text(chunk: ChunkRecord) -> str:
            path = self._repo_root / chunk.path
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            start_idx = max(0, chunk.start_line - 1)
            end_idx = min(len(lines), chunk.end_line)
            return "\n".join(lines[start_idx:end_idx])

        result = store.refresh(chunks, read_chunk_text=_read_chunk_text, embedder=embedder)
        return {
            "embedded": result.embedded,
            "reused": result.reused,
            "removed": result.removed,
            "failed": result.failed,
        }
```

Add the `SemanticNotAvailableError` exception class near the top of the file, alongside the existing `IndexSchemaUnsupportedError`:

```python
class SemanticNotAvailableError(Exception):
    """Raised when semantic/hybrid search is requested but not available."""
```

This new exception must be re-exported from the package so other modules can
import it as `from repo_mcp.index import SemanticNotAvailableError` (matching
how `IndexManager`/`IndexSchemaUnsupportedError` are already re-exported).
In `src/repo_mcp/index/__init__.py`, change:

```python
from .manager import INDEX_SCHEMA_VERSION, IndexManager, IndexSchemaUnsupportedError, IndexStatus
```

to:

```python
from .manager import (
    INDEX_SCHEMA_VERSION,
    IndexManager,
    IndexSchemaUnsupportedError,
    IndexStatus,
    SemanticNotAvailableError,
)
```

and add `"SemanticNotAvailableError",` to the `__all__` list in the same file.

Note on `refresh_semantic_index`: this is deliberately **not** called automatically from `refresh()` (per the design's bootstrap requirement — a plain `repo.refresh_index` must never trigger a model download). It's invoked lazily, the first time `search(mode="semantic"|"hybrid")` actually needs vectors that aren't there yet. Add this call inside `_semantic_search_hits`, before computing `scoped_vectors`, so the first semantic-mode call both downloads the model (via `_get_embedder()`, already happening in `_embed_query`) and backfills any missing chunk embeddings in the same call:

```python
    def _semantic_search_hits(
        self, *, query: str, top_k: int, filtered: list[SearchDocument]
    ) -> list[dict[str, object]]:
        self.refresh_semantic_index()
        allowed_paths = {doc.path for doc in filtered}
        ...
```

(Insert that `self.refresh_semantic_index()` call as the first line of the existing `_semantic_search_hits` body written above.)

- [ ] **Step 4: Update `repo.search`'s tool schema and handler validation**

In `src/repo_mcp/tools/schemas.py`, locate the `"repo.search"` entry's `"mode"` property (symbolic anchor: the `mode` field under `repo.search`'s `inputSchema.properties`) and update its description to mention the new values:

```python
                "mode": {
                    "type": "string",
                    "description": (
                        "Search mode: 'bm25' (default, always available), "
                        "'semantic' (requires the semantic extra + cached model), "
                        "or 'hybrid' (BM25+semantic fused via Reciprocal Rank Fusion)."
                    ),
                },
```

In `src/repo_mcp/tools/builtin.py`, locate `_search_handler` (symbolic anchor: the function validating `mode_value`). Replace the mode validation block:

```python
        if mode_value != "bm25":
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.search mode must be 'bm25' in v1.",
            )
```

with:

```python
        if mode_value not in ("bm25", "semantic", "hybrid"):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.search mode must be one of: bm25, semantic, hybrid.",
            )
```

Locate the call to `search_index(...)` near the end of `_search_handler` and add `mode_value` as an argument; update `search_index`'s type alias in the same file's parameter list from
`Callable[[str, int, str | None, str | None], list[dict[str, object]]]` to
`Callable[[str, int, str | None, str | None, str], list[dict[str, object]]]`, and the call site from:

```python
        hits = search_index(
            query_value,
            top_k_value,
            file_glob,
            path_prefix,
        )
        return {"hits": hits}
```

to:

```python
        try:
            hits = search_index(
                query_value,
                top_k_value,
                file_glob,
                path_prefix,
                mode_value,
            )
        except SemanticNotAvailableError as error:
            raise ToolDispatchError(code="SEMANTIC_NOT_AVAILABLE", message=str(error)) from error
        return {"hits": hits}
```

Add the import at the top of `tools/builtin.py`:

```python
from repo_mcp.index.manager import SemanticNotAvailableError
```

- [ ] **Step 5: Wire `IndexManager.search` into `register_builtin_tools`**

In `src/repo_mcp/server.py`, locate where `search_index=self._index_manager.search` is passed into `register_builtin_tools(...)` (this line is unchanged — `self._index_manager.search` now accepts the new `mode` parameter with a default, so the existing wiring keeps working as-is; only `tools/builtin.py`'s call to it needs the extra positional argument, already handled in Step 4).

- [ ] **Step 6: Wire `repo.status`'s new fields**

In `src/repo_mcp/tools/builtin.py`, locate `_status_handler` (symbolic anchor: the function building the `repo.status` result dict) and add a new parameter `semantic_status: Callable[[], tuple[bool, str]]` to its outer factory function signature, then add to the returned dict (alongside the existing `"limits_summary"`/`"chunking_summary"` keys):

```python
        semantic_available, semantic_model_status = semantic_status()
        return {
            "repo_root": str(repo_root),
            "index_status": index_status.index_status,
            "last_refresh_timestamp": index_status.last_refresh_timestamp,
            "indexed_file_count": index_status.indexed_file_count,
            "enabled_adapters": enabled_adapters,
            "semantic_available": semantic_available,
            "semantic_model_status": semantic_model_status,
            "limits_summary": {
                ...  # unchanged, keep existing keys
            },
            "chunking_summary": {
                ...  # unchanged, keep existing keys
            },
            "effective_config": config.to_public_dict(),
        }
```

Update `register_builtin_tools`'s call to `_status_handler(...)` to pass `self._index_manager.semantic_status` as the new argument, and update `register_builtin_tools`'s own signature to accept and forward a `semantic_status: Callable[[], tuple[bool, str]]` parameter, wired from `server.py`'s `register_builtin_tools(...)` call site as `semantic_status=self._index_manager.semantic_status`.

In `src/repo_mcp/tools/schemas.py`, locate the `"repo.status"` entry's description and append a note: `"Includes semantic_available and semantic_model_status to indicate whether semantic/hybrid search is currently usable."`

- [ ] **Step 7: Run the new tests**

Run: `python -m pytest tests/integration/test_repo_search_semantic_modes.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS. Pay particular attention to any existing test that calls `IndexManager.search(...)` positionally with exactly 4 arguments — the new `mode` parameter has a default (`"bm25"`), so existing positional calls remain valid, but double-check none pass exactly `(query, top_k, file_glob, path_prefix, <something extra>)` already.

- [ ] **Step 9: Commit**

```bash
git add src/repo_mcp/index/manager.py src/repo_mcp/index/__init__.py src/repo_mcp/tools/schemas.py src/repo_mcp/tools/builtin.py src/repo_mcp/server.py tests/integration/test_repo_search_semantic_modes.py
git commit -m "$(cat <<'EOF'
feat: add semantic/hybrid repo.search modes and repo.status fields

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Opt-in semantic-aware `repo.build_context_bundle`

**Files:**
- Modify: `src/repo_mcp/tools/schemas.py` (symbolic anchor: `"repo.build_context_bundle"` entry)
- Modify: `src/repo_mcp/tools/builtin.py` (symbolic anchor: `_build_context_bundle_handler`)
- Modify: `src/repo_mcp/server.py` (symbolic anchor: `StdioServer._build_context_bundle`)
- Test: `tests/integration/test_bundle_retrieval_mode.py` (new)

**Design note (read before editing):** `repo.build_context_bundle` already has a `strategy` field locked to `"hybrid"`, meaning the bundler's existing multi-query (prompt + extracted keywords) BM25 retrieval approach — that name is unrelated to this task's BM25+semantic fusion. To avoid a confusing same-word-different-meaning collision, this task adds a **new, separately-named** field, `retrieval_mode` (values `"bm25"` default / `"semantic"` / `"hybrid"` — yes, `"hybrid"` is reused as a value here too, but for a different field; `strategy="hybrid"` and `retrieval_mode="hybrid"` are independent settings and both must be documented as such in `SPEC.md` in Task 8). Do not rename `strategy` or attempt to merge the two concepts.

**Interfaces:**
- Consumes: nothing new — reuses `IndexManager.search` (Task 6, now mode-aware).
- Produces: `repo.build_context_bundle` accepts an optional `retrieval_mode` argument (default `"bm25"`, matching today's behavior exactly when omitted).

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_bundle_retrieval_mode.py`:

```python
from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_bundle_default_retrieval_mode_is_bm25_and_unaffected(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-1",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
        },
    )
    assert not is_tool_error(response)


def test_bundle_semantic_retrieval_mode_without_extra_returns_explicit_error(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-2",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
            "retrieval_mode": "semantic",
        },
    )
    assert is_tool_error(response)


def test_bundle_rejects_invalid_retrieval_mode(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))
    call_tool(server, "req-seed", "repo.refresh_index", {"force": False})

    response = call_tool(
        server,
        "req-bundle-3",
        "repo.build_context_bundle",
        {
            "prompt": "handler",
            "budget": {"max_files": 2, "max_total_lines": 20},
            "strategy": "hybrid",
            "include_tests": True,
            "retrieval_mode": "not-a-real-mode",
        },
    )
    assert is_tool_error(response)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_bundle_retrieval_mode.py -v`
Expected: the first test (default mode) currently PASSES already (no behavior change needed for the default case); the second and third FAIL because `retrieval_mode` is silently ignored (no validation exists yet, so an invalid value doesn't error, and a `"semantic"` value doesn't actually invoke semantic search or error out — both pass through to a normal BM25 bundle and return success instead of the expected error).

- [ ] **Step 3: Add `retrieval_mode` validation in `tools/builtin.py`**

In `src/repo_mcp/tools/builtin.py`, locate `_build_context_bundle_handler` (symbolic anchor: the function validating `strategy`). After the existing `strategy` validation block, add:

```python
        retrieval_mode = arguments.get("retrieval_mode", "bm25")
        if not isinstance(retrieval_mode, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle retrieval_mode must be a string.",
            )
        if retrieval_mode not in ("bm25", "semantic", "hybrid"):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle retrieval_mode must be one of: bm25, semantic, hybrid.",
            )
```

Add `"retrieval_mode": retrieval_mode,` to the dict passed into `build_context_bundle(...)` at the end of the handler (alongside the existing `"prompt"`, `"budget"`, `"strategy"`, `"include_tests"` keys).

- [ ] **Step 4: Thread `retrieval_mode` through to the bundler's `search_fn`**

In `src/repo_mcp/server.py`, locate `StdioServer._build_context_bundle` (symbolic anchor: where `arguments.get("prompt")`, `arguments.get("budget")` etc. are read, and where `search_fn=self._index_manager.search` is passed into `build_context_bundle(...)`). Add reading of the new argument:

```python
        retrieval_mode_value = arguments.get("retrieval_mode", "bm25")
        if not isinstance(retrieval_mode_value, str) or retrieval_mode_value not in (
            "bm25",
            "semantic",
            "hybrid",
        ):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.build_context_bundle retrieval_mode must be one of: bm25, semantic, hybrid.",
            )
```

Then change the `search_fn=self._index_manager.search` line to wrap it with the resolved mode:

```python
        def _mode_aware_search(
            query: str, top_k: int, file_glob: str | None, path_prefix: str | None
        ) -> list[dict[str, object]]:
            return self._index_manager.search(
                query, top_k, file_glob, path_prefix, retrieval_mode_value
            )

        result = build_context_bundle(
            prompt=prompt,
            budget=BundleBudget(max_files=max_files, max_total_lines=max_total_lines),
            search_fn=_mode_aware_search,
            read_lines_fn=self._read_repo_lines,
            outline_fn=self._bundle_outline_symbols,
            reference_lookup_fn=reference_lookup_fn,
            reference_lookup_many_fn=reference_lookup_many_fn,
            reference_lookup_scoped_many_fn=reference_lookup_scoped_many_fn,
            include_tests=include_tests,
            strategy="hybrid",
            top_k_per_query=self._limits.max_search_hits,
            profile_sink=self._write_bundler_profile if self._bundler_profile_enabled else None,
        )
```

Wrap the whole `build_context_bundle(...)` call (and the `_mode_aware_search` def above it) so that a `SemanticNotAvailableError` raised inside the bundler's internal search calls surfaces as a tool error rather than an unhandled exception:

```python
        try:
            result = build_context_bundle(
                ...  # as above
            )
        except SemanticNotAvailableError as error:
            raise ToolDispatchError(code="SEMANTIC_NOT_AVAILABLE", message=str(error)) from error
```

Add `SemanticNotAvailableError` to `server.py`'s existing `from repo_mcp.index import IndexManager, IndexSchemaUnsupportedError, discover_files` import line (extend it to also import `SemanticNotAvailableError`).

- [ ] **Step 5: Update the tool schema**

In `src/repo_mcp/tools/schemas.py`, locate the `"repo.build_context_bundle"` entry's `inputSchema.properties` (symbolic anchor: alongside `prompt`, `budget`, `strategy`, `include_tests`) and add:

```python
                "retrieval_mode": {
                    "type": "string",
                    "description": (
                        "Optional retrieval backend: 'bm25' (default), 'semantic' "
                        "(requires the semantic extra), or 'hybrid' (BM25+semantic via RRF). "
                        "Independent of 'strategy', which controls multi-query construction."
                    ),
                },
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_bundle_retrieval_mode.py -v`
Expected: PASS.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/repo_mcp/tools/builtin.py src/repo_mcp/server.py src/repo_mcp/tools/schemas.py tests/integration/test_bundle_retrieval_mode.py
git commit -m "$(cat <<'EOF'
feat: add opt-in retrieval_mode to repo.build_context_bundle

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: SPEC.md, README, and docs

**Files:**
- Modify: `SPEC.md`
- Modify: `README.md`
- Modify: `docs/AI_INTEGRATION.md`
- Modify: `docs/USAGE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `SPEC.md` §11.5 (`repo.search`)**

Locate the `### 11.5 \`repo.search\`` section. Change the `mode = "bm25"` input line to:

```
* `mode` = `"bm25"` (default) | `"semantic"` | `"hybrid"`
```

After the existing "Returns" bullet list, add:

```markdown
Mode notes:

* `"bm25"` is always available and is the default.
* `"semantic"` and `"hybrid"` require the optional `semantic` install extra
  and a cached local embedding model; requesting them without both returns
  an explicit error, never a silent fallback to `"bm25"`.
* `"hybrid"` fuses BM25 and semantic rankings via Reciprocal Rank Fusion
  (RRF): `score = sum(1 / (60 + rank))` over each ranked list a candidate
  appears in (1-based rank, candidates absent from a list contribute 0 for
  it). This is rank-based, not a weighted sum of raw scores, so no score
  normalization scheme is required and the fusion stays well-defined as the
  corpus changes. See `ADR-0018`.
```

- [ ] **Step 2: Update `SPEC.md` §11.1 (`repo.status`)**

Locate the `### 11.1 \`repo.status\`` "Returns" bullet list and add two new bullets:

```
* semantic_available (bool — whether the `semantic` extra is installed)
* semantic_model_status (`"not_installed"` | `"not_downloaded"` | `"ready"`)
```

- [ ] **Step 3: Update `SPEC.md` §11.7 (`repo.build_context_bundle`)**

Locate the `### 11.7 \`repo.build_context_bundle\`` "Inputs" bullet list (`prompt`, `budget`, `strategy = "hybrid"`, `include_tests`) and add:

```
* `retrieval_mode?` = `"bm25"` (default) | `"semantic"` | `"hybrid"` — independent
  of `strategy`; `strategy` controls multi-query construction, `retrieval_mode`
  controls the search backend (see §11.5).
```

- [ ] **Step 4: Update `README.md`, `docs/AI_INTEGRATION.md`, `docs/USAGE.md`**

In `README.md`'s `## Tool Surface (Current)` list, no new bullet is needed (no new tool name — `repo.search` and `repo.build_context_bundle` already listed). Instead add a short subsection after the tool list:

```markdown
## Optional Semantic Search

Install the `semantic` extra (`pip install repo-interrogator[semantic]`) to
enable `mode="semantic"`/`"hybrid"` on `repo.search` and `retrieval_mode` on
`repo.build_context_bundle`. The core package has zero runtime dependencies
and is unaffected when this extra isn't installed. See `ADR-0018` and
`docs/USAGE.md` for details.
```

In `docs/AI_INTEGRATION.md`, in the `## Available Tools` table, no row changes are needed (no new tool); add one sentence to the `repo.search` row's purpose text noting `(bm25 default; semantic/hybrid optional)`, or append a short paragraph below the table:

```markdown
`repo.search` and `repo.build_context_bundle` support optional semantic/hybrid
retrieval modes when the `semantic` install extra is present — see `docs/USAGE.md`.
```

In `docs/USAGE.md`, after the existing `## \`repo.search\`` section (find it by heading text, not line number — Track A's `## \`repo.find_definition\`` section may now sit nearby depending on insertion order), add:

```markdown
## Semantic / Hybrid Search (optional)

Requires `pip install repo-interrogator[semantic]` and a one-time model
download (triggered automatically on first `semantic`/`hybrid` call).

- `repo.search` `mode`: `"bm25"` (default) | `"semantic"` | `"hybrid"`.
- `repo.build_context_bundle` `retrieval_mode`: same three values, independent
  of `strategy`.
- `repo.status` reports `semantic_available` and `semantic_model_status` so a
  client can check before attempting semantic mode.
- `"hybrid"` uses Reciprocal Rank Fusion over BM25 and semantic rank
  positions — see `SPEC.md` §11.5 for the exact formula.
- Requesting `semantic`/`hybrid` without the extra installed, or before the
  model has finished its first download, returns an explicit tool error.
```

- [ ] **Step 5: Commit**

```bash
git add SPEC.md README.md docs/AI_INTEGRATION.md docs/USAGE.md
git commit -m "$(cat <<'EOF'
docs: document optional semantic/hybrid search modes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Final verification

**Files:** none (verification only, plus whatever Step 1 auto-fixes).

- [ ] **Step 1: Run formatting, linting, and type checks**

Run:
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
```
Expected: no errors. If `mypy` flags the optional `onnxruntime`/`tokenizers` imports in `embedder.py` (no bundled type stubs), add a `# type: ignore[import-untyped]` on those two import lines rather than loosening `mypy`'s strict mode project-wide.

- [ ] **Step 2: Run the full test suite without the `semantic` extra installed**

Run: `python -m pytest -q`
Expected: all tests PASS. This confirms the core package genuinely works with zero new dependencies present.

- [ ] **Step 3: Run the full test suite with the `semantic` extra installed**

Run:
```bash
python -m pip install -e ".[semantic]"
python -m pytest -q
```
Expected: all tests still PASS (the extra being present must not change any test's expected outcome, since this plan's tests are deliberately written to not depend on the real model being downloaded).

- [ ] **Step 4: Manual smoke test of the real download-and-embed path (not part of automated CI)**

This step exercises the one thing automated tests deliberately don't (no network in tests): the real pinned model. Run once, locally, after Task 2 Step 5's checksum constants are filled in:

```bash
python -c "
from pathlib import Path
import tempfile
from repo_mcp.semantic.model_cache import ModelCache, DEFAULT_MODEL_SPEC
from repo_mcp.semantic.embedder import Embedder

with tempfile.TemporaryDirectory() as tmp:
    cache = ModelCache(spec=DEFAULT_MODEL_SPEC)
    files = cache.ensure_model(Path(tmp))
    embedder = Embedder(files)
    vector = embedder.embed('hello world')
    print(len(vector), vector[:5])
"
```
Expected: downloads succeed, checksums verify, prints a vector of length 384 (the model's embedding dimension) with no exceptions. If `session.get_inputs()` names don't match what `embedder.py` expects (`input_ids`, `attention_mask`, optionally `token_type_ids`), inspect the printed `[i.name for i in session.get_inputs()]` from a quick interactive check and adjust `Embedder.embed`'s `feed` dict keys to match the actual exported model's input names.

- [ ] **Step 5: Final commit if Step 1 produced any auto-fixes**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: final formatting pass for semantic search work

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
