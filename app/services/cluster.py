"""Group phrases into sentence-pattern clusters by cosine similarity."""

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from app.models import Phrase
from app.services.normalize import match_key

# TF-IDF default calibrated in R006; embedding default from the R008 full-run trial.
CLUSTER_SIMILARITY = 0.55
EMBEDDING_SIMILARITY = 0.8
_NGRAM_RANGE = (2, 4)
_MAX_TEXT_CHARS = 300
_CHUNK_ROWS = 512


def tfidf_matrix(phrases: list[Phrase]) -> sparse.csr_matrix:
    """Character n-gram TF-IDF rows (L2-normalized) over masked phrase keys."""
    texts = [match_key(p.norm_key)[:_MAX_TEXT_CHARS] for p in phrases]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=_NGRAM_RANGE, sublinear_tf=True)
    return sparse.csr_matrix(vectorizer.fit_transform(texts))


def leader_cluster(matrix: sparse.csr_matrix | np.ndarray, similarity: float) -> list[list[int]]:
    """Leader clustering over L2-normalized rows ordered by priority (row 0 first).

    Each row joins the most similar existing leader when cosine similarity reaches
    ``similarity``; otherwise it becomes a new leader. Leaders are the earliest rows,
    so clusters have no chaining drift. Returns row indices per cluster, leader first.
    """
    clusters: list[list[int]] = []
    leaders: list[int] = []
    rows = matrix.shape[0] if isinstance(matrix, np.ndarray) else matrix.get_shape()[0]
    for start in range(0, rows, _CHUNK_ROWS):
        product = matrix[start : start + _CHUNK_ROWS] @ matrix.T
        block = product if isinstance(product, np.ndarray) else product.toarray()
        for offset in range(block.shape[0]):
            index = start + offset
            if leaders:
                sims = block[offset, leaders]
                best = int(np.argmax(sims))
                if sims[best] >= similarity:
                    clusters[best].append(index)
                    continue
            leaders.append(index)
            clusters.append([index])
    return clusters


def cluster_phrases(phrases: list[Phrase], similarity: float = CLUSTER_SIMILARITY) -> list[list[int]]:
    """TF-IDF leader clustering over phrases ordered by descending count."""
    if not phrases:
        return []
    return leader_cluster(tfidf_matrix(phrases), similarity)
