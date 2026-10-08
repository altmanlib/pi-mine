"""Optional SiliconFlow embeddings for phrase texts, with a local vector cache.

Only normalized phrase representative texts are sent; see
docs/design/2026-10-08-02-optional-embedding.md for the data boundary.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.services.fsutil import atomic_binary_writer

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_DIMENSIONS = 1024
EMBEDDINGS_CACHE_FILENAME = "embeddings.npz"

_BATCH_SIZE = 128
# Server latency per batch varies from 1s to 100s+; a few concurrent requests hide it.
_MAX_WORKERS = 4
_MAX_INPUT_CHARS = 1000
_MAX_ATTEMPTS = 4
_TIMEOUT_SECONDS = 120
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

type Fetcher = Callable[[list[str]], list[list[float]]]


class EmbeddingError(RuntimeError):
    """Embedding configuration or request failure."""


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    base_url: str
    api_key: str
    model: str = EMBEDDING_MODEL
    dimensions: int = EMBEDDING_DIMENSIONS

    @classmethod
    def from_env(cls) -> EmbeddingConfig:
        base_url = os.environ.get("SILICONFLOW_BASE_URL", "").rstrip("/")
        api_key = os.environ.get("SILICONFLOW_API_KEY", "")
        if not base_url or not api_key:
            raise EmbeddingError("SILICONFLOW_BASE_URL and SILICONFLOW_API_KEY must be set for --embedding")
        return cls(base_url=base_url, api_key=api_key)


def siliconflow_fetcher(config: EmbeddingConfig) -> Fetcher:
    """Build a batch fetcher calling the OpenAI-compatible embeddings endpoint with retries."""

    def fetch(batch: list[str]) -> list[list[float]]:
        rows = sorted(_post(batch)["data"], key=lambda item: item["index"])
        return [row["embedding"] for row in rows]

    def _post(batch: list[str]) -> dict[str, Any]:
        body = json.dumps(
            {"model": config.model, "input": batch, "dimensions": config.dimensions, "encoding_format": "float"}
        ).encode()
        request = urllib.request.Request(
            f"{config.base_url}/embeddings",
            data=body,
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS:
                    detail = error.read()[:300].decode(errors="replace")
                    raise EmbeddingError(f"embeddings request failed: HTTP {error.code} {detail}") from error
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == _MAX_ATTEMPTS:
                    raise EmbeddingError(f"embeddings request failed: {error}") from error
            time.sleep(2**attempt)
        raise EmbeddingError("embeddings request failed: retries exhausted")

    return fetch


def _cache_key(model: str, dimensions: int, text: str) -> str:
    return hashlib.sha256(f"{model}\x00{dimensions}\x00{text}".encode()).hexdigest()


def _load_cache(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        return {}
    with np.load(path) as data:
        return dict(zip(data["keys"].tolist(), data["vectors"], strict=True))


def _save_cache(path: Path, cache: dict[str, np.ndarray]) -> None:
    keys = np.array(list(cache), dtype=str)
    vectors = np.stack(list(cache.values())).astype(np.float32)
    with atomic_binary_writer(path) as handle:
        np.savez(handle, keys=keys, vectors=vectors)


def embed_texts(
    texts: Sequence[str],
    fetch: Fetcher,
    cache_path: Path,
    model: str = EMBEDDING_MODEL,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> np.ndarray:
    """Return L2-normalized vectors for texts, fetching only those missing from the cache."""
    inputs = [text[:_MAX_INPUT_CHARS] for text in texts]
    keys = [_cache_key(model, dimensions, text) for text in inputs]
    cache = _load_cache(cache_path)

    first_index: dict[str, int] = {}
    for i, key in enumerate(keys):
        if key not in cache:
            first_index.setdefault(key, i)
    missing = list(first_index.values())
    batches = [missing[start : start + _BATCH_SIZE] for start in range(0, len(missing), _BATCH_SIZE)]
    executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    try:
        futures = {executor.submit(fetch, [inputs[i] for i in batch]): batch for batch in batches}
        failures: list[Exception] = []
        for future in as_completed(futures):
            batch = futures[future]
            try:
                vectors = future.result()
            except Exception as error:  # re-raised below after keeping other batches
                failures.append(error)
                continue
            if len(vectors) != len(batch):
                failures.append(EmbeddingError(f"expected {len(batch)} vectors, got {len(vectors)}"))
                continue
            for i, vector in zip(batch, vectors, strict=True):
                cache[keys[i]] = np.asarray(vector, dtype=np.float32)
        if failures:
            raise failures[0]
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        # Keep vectors fetched so far, so an interrupted run resumes instead of re-sending.
        if missing and cache:
            _save_cache(cache_path, cache)

    if not texts:
        return np.zeros((0, dimensions), dtype=np.float32)
    matrix = np.stack([cache[key] for key in keys])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)
