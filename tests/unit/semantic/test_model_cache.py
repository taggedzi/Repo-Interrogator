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
