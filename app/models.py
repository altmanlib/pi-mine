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
