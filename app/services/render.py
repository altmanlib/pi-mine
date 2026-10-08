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


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


# Main review sections: (title, kind, destination hint). Only strong candidates appear here.
_MAIN_SECTIONS = (
    ("约束与红线", "constraint", "AGENTS"),
    ("偏好", "preference", "AGENTS"),
    ("工具习惯", "tooling", "AGENTS"),
    ("工作流", "workflow", "skill / prompt"),
)


def _variants_cell(candidate: Candidate) -> str:
    """Show merged variant patterns with counts; empty when the cluster has a single pattern."""
    if candidate.variant_count == 1:
        return ""
    shown = " · ".join(f"{_cell(v.text)} ×{v.count}" for v in candidate.variants)
    hidden = candidate.variant_count - len(candidate.variants)
    return f"{shown} · 另 {hidden} 种" if hidden > 0 else shown


def _table(rows: list[tuple[int, Candidate]], *, with_kind: bool = False) -> list[str]:
    if not rows:
        return ["无", ""]
    head = "| # | 句式 | 次数 | 项目 |" + (" 类型 | 建议 |" if with_kind else "") + " 变体 |"
    sep = "|---|---|---|---|" + ("---|---|" if with_kind else "") + "---|"
    lines = [head, sep]
    for number, c in rows:
        extra = f" {c.kind} | {c.suggested_dest} |" if with_kind else ""
        lines.append(f"| {number} | {_cell(c.label)} | {c.count} | {c.project_count} |{extra} {_variants_cell(c)} |")
    return [*lines, ""]


def _template_list(rows: list[tuple[int, Candidate]]) -> list[str]:
    if not rows:
        return ["无", ""]
    return [*(f"- #{n} {_cell(c.label)}（{c.count} 次 / {c.project_count} 项目）" for n, c in rows), ""]


def render_candidates_md(candidates: list[Candidate], summary: MineSummary) -> str:
    """Group candidates by review destination; numbering is global across sections."""
    strong = [c for c in candidates if c.confidence == "strong"]
    groups: list[tuple[str, list[Candidate]]] = [
        (f"{title} → {dest}", [c for c in strong if c.kind == kind]) for title, kind, dest in _MAIN_SECTIONS
    ]
    groups += [
        ("附录 A：未分类（strong）", [c for c in strong if c.kind == "other"]),
        ("附录 B：覆盖不足（medium）", [c for c in candidates if c.confidence == "medium" and c.kind != "template"]),
        ("附录 C：模板展开文本", [c for c in candidates if c.kind == "template"]),
    ]

    lines = [
        "# 资产候选",
        "",
        f"- 发言 {summary.utterance_count} → 句子 {summary.phrase_count} → 簇 {summary.cluster_count}"
        f" → 候选 {summary.candidate_count}（strong {summary.strong_count}）",
        f"- 聚类：{summary.cluster_backend}；阈值：min-count {summary.min_count}，min-projects {summary.min_projects}",
        "- 句式中 ‹路径› / ‹数字› 为参数占位；变体列为簇内合并的不同写法及次数",
        "",
    ]
    number = 0
    for title, members in groups:
        rows: list[tuple[int, Candidate]] = []
        for candidate in members:
            number += 1
            rows.append((number, candidate))
        lines += [f"## {title}（{len(members)}）", ""]
        if title.startswith("附录 C"):
            lines += _template_list(rows)
        else:
            lines += _table(rows, with_kind=title.startswith("附录 B"))
    return "\n".join(lines).rstrip() + "\n"


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
        *([f"  - {_cell(p.text[:80])} (count {p.count})" for p in top_corrections] or ["  - None"]),
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
        *[f"| {_cell(display_cwd(project_cwd[key]))} | {n} |" for key, n in project_counts.most_common(_TOP_PROJECTS)],
    ]
    return "\n".join(lines) + "\n"
