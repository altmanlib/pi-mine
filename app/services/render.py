"""Render candidates and persona documents."""

import json
import re
from collections import Counter

from app.models import Candidate, MineSummary, Phrase, Utterance
from app.services.rank import classify_kind

_TOP_PROJECTS = 10
_TOP_ITEMS = 8
_HOME_PREFIX_RE = re.compile(r"^/(?:Users|home)/[^/]+")


def display_cwd(cwd: str) -> str:
    """Show a working directory with the home prefix written as ``~``."""
    return _HOME_PREFIX_RE.sub("~", cwd)


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_candidates_md(candidates: list[Candidate], summary: MineSummary) -> str:
    lines = [
        "# Candidates",
        "",
        f"- utterances: {summary.utterance_count}",
        f"- phrases: {summary.phrase_count}",
        f"- clusters: {summary.cluster_count}",
        f"- candidates: {summary.candidate_count} (strong {summary.strong_count})",
        f"- thresholds: min-count {summary.min_count}, min-projects {summary.min_projects}",
        "",
        "## Overview",
        "",
        "| # | confidence | kind | dest | count | projects | days | label |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for number, c in enumerate(candidates, start=1):
        lines.append(
            f"| {number} | {c.confidence} | {c.kind} | {c.suggested_dest} | {c.count} | {c.project_count} | {c.day_span} "
            f"| {_escape_cell(c.label)} |"
        )

    lines += ["", "## Strong candidates", ""]
    strong = [(n, c) for n, c in enumerate(candidates, start=1) if c.confidence == "strong"]
    if not strong:
        lines.append("None")
    for number, c in strong:
        lines += [
            f"### {number}. {c.label}",
            "",
            f"- id: `{c.candidate_id}`",
            f"- kind: {c.kind} → {c.suggested_dest}",
            f"- count {c.count} / projects {c.project_count} / days {c.day_span}",
            "- samples:",
            *[f"  - {_escape_inline(text)}" for text in c.sample_texts],
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _escape_inline(text: str) -> str:
    return text.replace("\n", " ")


def render_candidates_json(candidates: list[Candidate], summary: MineSummary) -> str:
    payload = {"summary": summary.to_dict(), "candidates": [c.to_dict() for c in candidates]}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_persona(
    candidates: list[Candidate],
    phrases: list[Phrase],
    utterances: list[Utterance],
) -> str:
    total = sum(p.count for p in phrases)
    corrections = [p for p in phrases if classify_kind(p) == "constraint"]
    correction = sum(p.count for p in corrections)
    share = f"{correction / total:.1%}" if total else "n/a"
    top_corrections = corrections[:_TOP_ITEMS]

    def labels(kinds: set[str], confidence: str) -> list[str]:
        picked = [c for c in candidates if c.kind in kinds and c.confidence == confidence]
        return [f"- {c.label} (count {c.count}, projects {c.project_count})" for c in picked[:_TOP_ITEMS]] or ["- None"]

    project_counts = Counter(u.project_key for u in utterances)
    project_cwd = {u.project_key: u.cwd for u in reversed(utterances)}
    lines = [
        "# Persona",
        "",
        "## Collaboration style",
        "",
        f"- utterances after merge: {total}",
        f"- correction / constraint share: {share} ({correction})",
        "- most frequent corrections:",
        *([f"  - {_escape_inline(p.text[:80])} (count {p.count})" for p in top_corrections] or ["  - None"]),
        "",
        "## Red lines (strong constraints)",
        "",
        *labels({"constraint"}, "strong"),
        "",
        "## Tooling and workflow habits (strong)",
        "",
        *labels({"tooling", "workflow"}, "strong"),
        "",
        "## Preferences (strong)",
        "",
        *labels({"preference"}, "strong"),
        "",
        "## Unstable patterns (frequent but narrow coverage)",
        "",
        *labels({"constraint", "preference", "tooling", "workflow", "other"}, "medium"),
        "",
        "## Project distribution",
        "",
        "| project | utterances |",
        "|---|---|",
        *[f"| {_escape_cell(display_cwd(project_cwd[key]))} | {n} |" for key, n in project_counts.most_common(_TOP_PROJECTS)],
    ]
    return "\n".join(lines) + "\n"
