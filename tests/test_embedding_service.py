"""Tests for the embedding cache and leader clustering on dense vectors."""

from pathlib import Path

import numpy as np
import pytest

from app.services.cluster import leader_cluster
from app.services.embedding import EmbeddingConfig, EmbeddingError, embed_texts


class FakeFetcher:
    """Deterministic fetcher that records every text it was asked to embed."""

    def __init__(self, dimensions: int = 3) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def __call__(self, batch: list[str]) -> list[list[float]]:
        self.calls.append(batch)
        return [[float(len(text)), 1.0, *[0.0] * (self.dimensions - 2)] for text in batch]


def test_embed_texts_normalizes_dedupes_and_caches(tmp_path: Path) -> None:
    cache = tmp_path / "embeddings.npz"
    fetch = FakeFetcher()
    matrix = embed_texts(["ab", "abcd", "ab"], fetch, cache, dimensions=3)

    assert fetch.calls == [["ab", "abcd"]]
    assert matrix.shape == (3, 3)
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0, rtol=1e-6)
    np.testing.assert_allclose(matrix[0], matrix[2])

    again = FakeFetcher()
    embed_texts(["abcd", "xyz"], again, cache, dimensions=3)
    assert again.calls == [["xyz"]]


def test_embed_texts_keeps_progress_when_a_batch_fails(tmp_path: Path) -> None:
    cache = tmp_path / "embeddings.npz"
    texts = [f"t{i}" for i in range(200)]
    calls = 0

    def flaky(batch: list[str]) -> list[list[float]]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise EmbeddingError("boom")
        return [[1.0, 0.0] for _ in batch]

    with pytest.raises(EmbeddingError):
        embed_texts(texts, flaky, cache, dimensions=2)

    resumed = FakeFetcher(dimensions=2)
    embed_texts(texts, resumed, cache, dimensions=2)
    assert sum(len(batch) for batch in resumed.calls) == 200 - 128


def test_embedding_config_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SILICONFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    with pytest.raises(EmbeddingError):
        EmbeddingConfig.from_env()

    monkeypatch.setenv("SILICONFLOW_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "k")
    assert EmbeddingConfig.from_env().base_url == "https://example.test/v1"


def test_leader_cluster_on_dense_vectors() -> None:
    vectors = np.array([[1.0, 0.0], [0.98, 0.2], [0.0, 1.0]])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    assert leader_cluster(vectors, 0.9) == [[0, 1], [2]]
