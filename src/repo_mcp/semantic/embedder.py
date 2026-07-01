"""ONNX-backed sentence embedding for semantic search (requires the `semantic` extra)."""

from __future__ import annotations

import math

from repo_mcp.semantic.model_cache import ModelFiles

try:
    import onnxruntime as ort  # type: ignore[import-not-found]
    from tokenizers import Tokenizer  # type: ignore[import-not-found]

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
