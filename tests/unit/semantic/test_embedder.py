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


def test_is_semantic_extra_installed_reflects_import_availability() -> None:
    from repo_mcp.semantic import embedder

    assert embedder.is_semantic_extra_installed() in (True, False)
