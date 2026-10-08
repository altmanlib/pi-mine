"""Shared data shapes for extract / mine stages."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Utterance:
    utterance_id: str
    session_id: str
    entry_id: str
    timestamp: str
    cwd: str
    project_key: str
    text: str
    char_len: int
    source_file: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Utterance:
        return cls(**data)


@dataclass(slots=True)
class ExtractResult:
    """Outcome of one extract run; counters are updated in place while scanning."""

    sessions_dir: str
    out_dir: str
    output_path: str
    session_file_count: int = 0
    utterance_count: int = 0
    project_count: int = 0
    skipped_slash: int = 0
    skipped_confirm: int = 0
    skipped_empty: int = 0
    skipped_no_session: int = 0
    skipped_malformed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Phrase:
    """Near-duplicate utterances merged under one representative text."""

    phrase_id: str
    text: str
    norm_key: str
    count: int
    project_keys: list[str]
    first_timestamp: str
    last_timestamp: str
    is_correction: bool
    utterance_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizeResult:
    phrases: list[Phrase]
    input_count: int
    fork_duplicate_count: int


@dataclass(slots=True)
class Variant:
    """One merged phrase inside a candidate cluster."""

    text: str
    count: int


@dataclass(slots=True)
class Candidate:
    candidate_id: str
    label: str
    count: int
    project_count: int
    day_span: int
    kind: str
    suggested_dest: str
    confidence: str
    variant_count: int
    variants: list[Variant]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MineSummary:
    """Outcome of one mine run."""

    out_dir: str
    min_count: int
    min_projects: int
    cluster_backend: str
    utterance_count: int
    phrase_count: int
    cluster_count: int
    candidate_count: int
    strong_count: int
    fork_duplicate_count: int
    candidates_md_path: str
    candidates_json_path: str
    persona_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
