"""Rank phrase clusters into graded asset candidates."""

import re
from datetime import date

from app.models import Candidate, Phrase, Variant
from app.services.normalize import mask_params

# v1 defaults, calibrated in R006.
STRONG_DAY_SPAN = 90
STRONG_SPAN_COUNT_FACTOR = 3
_TEMPLATE_MIN_CHARS = 200
_LABEL_CHARS = 60
_VARIANT_COUNT = 5
_VARIANT_CHARS = 40
_SKILL_NAME_RE = re.compile(r'<skill\s+name="([^"]+)"')
PATH_PLACEHOLDER = "‹路径›"
NUMBER_PLACEHOLDER = "‹数字›"

_TOOLING_RE = re.compile(
    r"\b(gh|git|tea|uv|bun|docker|ssh|npm|pnpm|pip|playwright|obscura|pytest|ruff|pyright|cargo|brew|make|orb)\b"
)
_WORKFLOW_RE = re.compile(r"\b(commit|push|pull|fix|review|plan|release|read|update|init|save|move)\b")
_WORKFLOW_MARKERS = (
    "提交",
    "推送",
    "执行",
    "开始",
    "实施",
    "修复",
    "审查",
    "方案",
    "计划",
    "发版",
    "发布",
    "合并",
    "清理",
    "整理",
    "创建",
    "新建",
    "检查",
    "修订",
    "修正",
    "更新",
    "阅读",
    "了解",
    "分析",
    "建议",
    "进度",
    "汇报",
    "下一步",
)
_PREFERENCE_MARKERS = ("请用", "使用", "优先", "默认", "简体", "中文", "习惯", "统一", "保持", "prefer", "always")

_DESTINATIONS: dict[tuple[str, str], str] = {
    ("constraint", "strong"): "AGENTS",
    ("constraint", "medium"): "notes",
    ("preference", "strong"): "AGENTS",
    ("preference", "medium"): "notes",
    ("tooling", "strong"): "AGENTS",
    ("tooling", "medium"): "notes",
    ("workflow", "strong"): "skill",
    ("workflow", "medium"): "prompt",
}
_CONFIDENCE_ORDER = {"strong": 0, "medium": 1}


def classify_kind(phrase: Phrase) -> str:
    """Coarse rule-based type: template / constraint / tooling / workflow / preference / other.

    ``template`` marks expanded skill or prompt-template text rather than hand-typed phrases.
    """
    key = phrase.norm_key
    if phrase.text.lstrip().startswith("<skill") or len(key) > _TEMPLATE_MIN_CHARS:
        return "template"
    if phrase.is_correction:
        return "constraint"
    if _TOOLING_RE.search(key):
        return "tooling"
    if _WORKFLOW_RE.search(key) or any(marker in key for marker in _WORKFLOW_MARKERS):
        return "workflow"
    if any(marker in key for marker in _PREFERENCE_MARKERS):
        return "preference"
    return "other"


def _is_bare_path(text: str) -> bool:
    """Return True for a single-token absolute or home path with no instruction around it."""
    stripped = text.strip()
    return stripped.startswith(("/", "~/")) and not any(char.isspace() for char in stripped)


def display_label(phrase: Phrase, kind: str) -> str:
    """Readable cluster label: masked sentence pattern, or a short title for templates."""
    if kind == "template":
        match = _SKILL_NAME_RE.search(phrase.text)
        if match:
            return f"skill: {match.group(1)}"
        first_line = next((line for line in phrase.text.splitlines() if line.strip()), phrase.text)
        return _clip(first_line.lstrip("# "), _LABEL_CHARS)
    return _clip(mask_params(phrase.text, PATH_PLACEHOLDER, NUMBER_PLACEHOLDER), _LABEL_CHARS)


def _variants(group: list[Phrase]) -> list[Variant]:
    """Aggregate cluster phrases by masked pattern, most frequent first."""
    totals: dict[str, int] = {}
    for p in group:
        pattern = _clip(mask_params(p.text, PATH_PLACEHOLDER, NUMBER_PLACEHOLDER), _VARIANT_CHARS)
        totals[pattern] = totals.get(pattern, 0) + p.count
    ordered = sorted(totals.items(), key=lambda item: -item[1])
    return [Variant(text=text, count=count) for text, count in ordered]


def _day_span(first: str, last: str) -> int:
    try:
        return (date.fromisoformat(last[:10]) - date.fromisoformat(first[:10])).days
    except ValueError:
        return 0


def _clip(text: str, limit: int) -> str:
    single = " ".join(text.split())
    return single if len(single) <= limit else single[: limit - 1] + "…"


def rank_clusters(
    phrases: list[Phrase],
    clusters: list[list[int]],
    min_count: int,
    min_projects: int,
) -> list[Candidate]:
    """Build candidates for clusters reaching ``min_count``; strong ones span projects or a long time."""
    candidates: list[Candidate] = []
    for members in clusters:
        group = [phrases[i] for i in members]
        count = sum(p.count for p in group)
        if count < min_count:
            continue
        leader = group[0]
        if _is_bare_path(leader.text):
            continue
        project_count = len({key for p in group for key in p.project_keys})
        day_span = _day_span(min(p.first_timestamp for p in group), max(p.last_timestamp for p in group))
        long_lived = day_span >= STRONG_DAY_SPAN and count >= STRONG_SPAN_COUNT_FACTOR * min_count
        confidence = "strong" if project_count >= min_projects or long_lived else "medium"
        kind = classify_kind(leader)
        variants = _variants(group)
        candidates.append(
            Candidate(
                candidate_id=leader.phrase_id,
                label=display_label(leader, kind),
                count=count,
                project_count=project_count,
                day_span=day_span,
                kind=kind,
                suggested_dest=_DESTINATIONS.get((kind, confidence), "observe"),
                confidence=confidence,
                variant_count=len(variants),
                variants=variants[:_VARIANT_COUNT],
            )
        )
    candidates.sort(key=lambda c: (_CONFIDENCE_ORDER[c.confidence], -c.count, -c.project_count, c.candidate_id))
    return candidates
