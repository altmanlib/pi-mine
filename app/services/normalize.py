"""Normalize utterances and merge near-duplicates into phrases."""

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict

from app.models import NormalizeResult, Phrase, Utterance

# Whole-utterance confirmations compared against the normalized key. Instructions such
# as "执行" or "开始" are intentionally absent: they are workflow triggers, not confirmations.
CONFIRM_KEYS = frozenset(
    {
        "好",
        "好的",
        "好吧",
        "行",
        "行吧",
        "嗯",
        "嗯嗯",
        "对",
        "对的",
        "是",
        "是的",
        "可以",
        "可以的",
        "没问题",
        "继续",
        "ok",
        "okay",
        "yes",
        "y",
        "continue",
    }
)

# Substrings of the normalized key that mark a correction or constraint.
CORRECTION_MARKERS = (
    "先别",
    "先不要",
    "不要",
    "别改",
    "只讨论",
    "不对",
    "不是",
    "停一下",
    "重新",
    "don't",
    "do not",
    "stop",
    "wait",
    "instead",
)

# Fuzzy merge parameters (v1 defaults, calibrated in R006).
FUZZY_MIN_CHARS = 4
FUZZY_MAX_CHARS = 200
FUZZY_JACCARD = 0.85


def normalize_key(text: str) -> str:
    """NFKC + casefold, collapse whitespace, strip surrounding punctuation and symbols."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    collapsed = " ".join(folded.split())
    start, end = 0, len(collapsed)
    while start < end and _is_edge_noise(collapsed[start]):
        start += 1
    while end > start and _is_edge_noise(collapsed[end - 1]):
        end -= 1
    return collapsed[start:end]


_PATH_RE = re.compile(r"\S*/\S*")
_NUMBER_RE = re.compile(r"\d+")


def match_key(norm_key: str) -> str:
    """Mask path-like tokens and numbers so parameterized variants of one phrase share a key.

    Keys that would contain only placeholders (bare paths, bare numbers) stay unmasked.
    """
    masked = _NUMBER_RE.sub("§n", _PATH_RE.sub("§p", norm_key))
    if not any(char.isalnum() for char in masked.replace("§n", "").replace("§p", "")):
        return norm_key
    return masked


def _is_edge_noise(char: str) -> bool:
    return unicodedata.category(char)[0] in {"P", "S", "Z"}


def is_confirm_utterance(text: str) -> bool:
    """Return True for low-information confirmation short replies."""
    return normalize_key(text) in CONFIRM_KEYS


def is_correction_key(norm_key: str) -> bool:
    """Return True when the normalized key contains a correction marker."""
    return any(marker in norm_key for marker in CORRECTION_MARKERS)


def _bigrams(key: str) -> frozenset[str]:
    return frozenset(key[i : i + 2] for i in range(len(key) - 1)) or frozenset({key})


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _fuzzy_pairs(keys: list[str]) -> list[tuple[int, int]]:
    """Return index pairs whose bigram Jaccard similarity reaches the threshold.

    Uses prefix filtering over a global rare-first token order, so common bigrams
    do not produce quadratic candidate sets.
    """
    eligible = [i for i, key in enumerate(keys) if FUZZY_MIN_CHARS <= len(key) <= FUZZY_MAX_CHARS]
    sets = {i: _bigrams(keys[i]) for i in eligible}
    document_frequency: Counter[str] = Counter()
    for tokens in sets.values():
        document_frequency.update(tokens)

    ordered = {i: sorted(tokens, key=lambda t: (document_frequency[t], t)) for i, tokens in sets.items()}
    index: dict[str, list[int]] = defaultdict(list)
    pairs: list[tuple[int, int]] = []

    for i in eligible:
        tokens = ordered[i]
        size = len(tokens)
        prefix_len = size - math.ceil(FUZZY_JACCARD * size) + 1
        seen: set[int] = set()
        for token in tokens[:prefix_len]:
            for j in index[token]:
                if j in seen:
                    continue
                seen.add(j)
                other = len(sets[j])
                if min(size, other) < FUZZY_JACCARD * max(size, other):
                    continue
                inter = len(sets[i] & sets[j])
                if inter / (size + other - inter) >= FUZZY_JACCARD:
                    pairs.append((j, i))
            index[token].append(i)
    return pairs


def _drop_fork_duplicates(utterances: list[Utterance]) -> tuple[list[Utterance], int]:
    """Drop copies of the same message replayed into forked sessions (same timestamp and text)."""
    seen: set[tuple[str, str]] = set()
    kept: list[Utterance] = []
    for utterance in utterances:
        marker = (utterance.timestamp, normalize_key(utterance.text))
        if marker in seen:
            continue
        seen.add(marker)
        kept.append(utterance)
    return kept, len(utterances) - len(kept)


def normalize_utterances(utterances: list[Utterance]) -> NormalizeResult:
    """Merge utterances into phrases by exact normalized key, then fuzzy similarity."""
    kept, dropped = _drop_fork_duplicates(utterances)

    by_key: dict[str, list[Utterance]] = defaultdict(list)
    for utterance in kept:
        key = normalize_key(utterance.text)
        if key:
            by_key[match_key(key)].append(utterance)

    keys = list(by_key)
    parent = list(range(len(keys)))
    for a, b in _fuzzy_pairs(keys):
        root_a, root_b = _find(parent, a), _find(parent, b)
        if root_a != root_b:
            parent[root_b] = root_a

    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(keys)):
        members[_find(parent, i)].append(i)

    phrases = [_build_phrase([keys[i] for i in group], by_key) for group in members.values()]
    phrases.sort(key=lambda p: (-p.count, p.norm_key))
    return NormalizeResult(phrases=phrases, input_count=len(utterances), fork_duplicate_count=dropped)


def _build_phrase(group_keys: list[str], by_key: dict[str, list[Utterance]]) -> Phrase:
    rows = sorted((u for key in group_keys for u in by_key[key]), key=lambda u: u.timestamp)
    # Representative: most frequent original text; ties resolve to the earliest occurrence.
    text_counts = Counter(u.text for u in rows)
    best = max(text_counts.values())
    text = next(u.text for u in rows if text_counts[u.text] == best)
    norm_key = normalize_key(text)
    return Phrase(
        phrase_id=hashlib.sha256(norm_key.encode()).hexdigest()[:12],
        text=text,
        norm_key=norm_key,
        count=len(rows),
        project_keys=sorted({u.project_key for u in rows}),
        first_timestamp=rows[0].timestamp,
        last_timestamp=rows[-1].timestamp,
        is_correction=is_correction_key(norm_key),
        utterance_ids=[u.utterance_id for u in rows],
    )
