"""Group phrases into sentence-pattern clusters with TF-IDF cosine similarity."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.models import Phrase
from app.services.normalize import match_key

# v1 defaults, calibrated in R006.
CLUSTER_SIMILARITY = 0.55
_NGRAM_RANGE = (2, 4)
_MAX_TEXT_CHARS = 300
_CHUNK_ROWS = 512


def cluster_phrases(phrases: list[Phrase], similarity: float = CLUSTER_SIMILARITY) -> list[list[int]]:
    """Leader clustering over phrases ordered by descending count.

    Each phrase joins the most similar existing leader when cosine similarity reaches
    ``similarity``; otherwise it becomes a new leader. Leaders are the highest-count
    members, so clusters have no chaining drift. Returns phrase indices per cluster,
    leader first, clusters ordered by leader position.
    """
    if not phrases:
        return []

    texts = [match_key(p.norm_key)[:_MAX_TEXT_CHARS] for p in phrases]
    matrix = TfidfVectorizer(analyzer="char", ngram_range=_NGRAM_RANGE, sublinear_tf=True).fit_transform(texts).tocsr()

    clusters: list[list[int]] = []
    leaders: list[int] = []
    for start in range(0, len(phrases), _CHUNK_ROWS):
        block = (matrix[start : start + _CHUNK_ROWS] @ matrix.T).toarray()
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
