"""Orchestrate normalize → cluster → rank → render from extracted utterances."""

from pathlib import Path

from app.models import MineSummary
from app.services.cluster import cluster_phrases
from app.services.extract import UTTERANCES_FILENAME, read_utterances
from app.services.fsutil import atomic_text_writer
from app.services.normalize import normalize_utterances
from app.services.rank import rank_clusters
from app.services.render import render_candidates_json, render_candidates_md, render_persona

CANDIDATES_MD = "candidates.md"
CANDIDATES_JSON = "candidates.json"
PERSONA_MD = "persona.md"


def _write(path: Path, content: str) -> None:
    with atomic_text_writer(path) as handle:
        handle.write(content)


def mine_utterances(out_dir: Path, min_count: int, min_projects: int) -> MineSummary:
    """Read ``utterances.jsonl`` from out_dir and write candidates and persona files."""
    source = out_dir / UTTERANCES_FILENAME
    if not source.is_file():
        raise FileNotFoundError(f"{source} not found; run extract first")

    utterances = read_utterances(source)
    normalized = normalize_utterances(utterances)
    clusters = cluster_phrases(normalized.phrases)
    candidates = rank_clusters(normalized.phrases, clusters, min_count, min_projects)

    summary = MineSummary(
        out_dir=str(out_dir),
        min_count=min_count,
        min_projects=min_projects,
        utterance_count=len(utterances),
        phrase_count=len(normalized.phrases),
        cluster_count=len(clusters),
        candidate_count=len(candidates),
        strong_count=sum(c.confidence == "strong" for c in candidates),
        fork_duplicate_count=normalized.fork_duplicate_count,
        candidates_md_path=str(out_dir / CANDIDATES_MD),
        candidates_json_path=str(out_dir / CANDIDATES_JSON),
        persona_path=str(out_dir / PERSONA_MD),
    )
    _write(out_dir / CANDIDATES_MD, render_candidates_md(candidates, summary))
    _write(out_dir / CANDIDATES_JSON, render_candidates_json(candidates, summary))
    _write(out_dir / PERSONA_MD, render_persona(candidates, normalized.phrases, utterances))
    return summary
