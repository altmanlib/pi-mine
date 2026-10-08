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
    sample_texts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
