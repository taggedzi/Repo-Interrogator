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


# TODO(semantic-search): these are PLACEHOLDER values, not a real pinned model.
# Before semantic/hybrid search can actually work, replace with real values by:
#   1. Resolving the exact commit SHA for the target model repo (e.g. via
#      `git ls-remote https://huggingface.co/Xenova/all-MiniLM-L6-v2 main`)
#   2. Downloading the model + tokenizer files from that exact commit
#   3. Computing sha256sum on each downloaded file
#   4. Replacing the values below with the real commit SHA and checksums
# Until then, ModelCache.ensure_model() using this spec will always fail: the
# placeholder URL is not a real Hugging Face resource, so `_download` raises
# urllib.error.HTTPError (401 Unauthorized) before a file is ever downloaded
# and checksum verification is reached. It will NOT raise ModelChecksumError.
DEFAULT_MODEL_SPEC = ModelSpec(
    model_url=(
        "https://huggingface.co/PLACEHOLDER/PLACEHOLDER/resolve/"
        "0000000000000000000000000000000000000000/onnx/model_quantized.onnx"
    ),
    model_sha256="0" * 64,
    tokenizer_url=(
        "https://huggingface.co/PLACEHOLDER/PLACEHOLDER/resolve/"
        "0000000000000000000000000000000000000000/tokenizer.json"
    ),
    tokenizer_sha256="0" * 64,
    cache_subdir=DEFAULT_MODEL_SPEC_CACHE_SUBDIR,
)
