"""Synthesize candidate clusters into evidence-backed conclusions with an LLM.

The LLM only proposes statements and cites candidate numbers. Evidence numbers are
validated locally and all counts are computed from candidates.json, never taken
from the LLM reply.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models import Candidate, Conclusion, SynthesisResult
from app.services.fsutil import atomic_text_writer
from app.services.llm import ChatFn, LlmError, parse_json_reply
from app.services.rank import review_section

CONCLUSIONS_MD = "conclusions.md"
CONCLUSIONS_JSON = "conclusions.json"

KINDS = ("constraint", "preference", "tooling", "workflow", "style")
DESTS = ("AGENTS", "skill", "prompt", "notes")
_DEST_TITLES = {
    "AGENTS": "写入 AGENTS 的规则",
    "skill": "做成 skill 的工作流",
    "prompt": "做成 prompt template 的指令",
    "notes": "记入 notes 的事实",
}


@dataclass(frozen=True, slots=True)
class _Group:
    title: str
    sections: tuple[str, ...]


# Prompt groups keep each request focused; templates are excluded (already codified as files).
_GROUPS = (
    _Group("约束、偏好与工具习惯（strong）", ("constraint", "preference", "tooling")),
    _Group("工作流指令（strong）", ("workflow",)),
    _Group("未分类与覆盖不足的候选：大部分是噪声，只提炼确有规律的部分", ("other", "medium")),
)

_SYSTEM = """你在分析一位开发者与 coding agent 对话时反复说过的话，目标是提炼可以沉淀的结论。

输入每行是一个候选簇：`#编号 [类型] 次数 N 项目 M | 句式 | 变体: 写法 ×次数; ...`。
句式中 ‹路径› / ‹数字› 是参数占位。簇由自动聚类得到，可能混入无关句子，或把相反意思（如「不要 X」与「缺少 X」）归在一起；只采信被多条变体共同支持的意思。

要求：
- 每条结论是一句可直接执行或可直接写入规则的中文陈述，例如「执行命令前不要每次都 cd 到项目目录」
- 合并说同一件事的多个候选；忽略一次性任务细节、业务内容、闲聊、无法判断意图的候选
- kind 取值：constraint（禁止或必须）、preference（偏好）、tooling（工具使用）、workflow（多步流程或推进节奏）、style（协作风格观察）
- dest 取值：AGENTS（对 agent 的长期约束或偏好）、skill（多步工作流）、prompt（可复用的一句话指令模板）、notes（与特定项目或环境相关的事实）
- evidence 只能引用输入中出现的编号，至少 1 个
- 宁缺毋滥：没有可靠结论时返回空数组

只输出 JSON：{"conclusions": [{"statement": "...", "kind": "...", "dest": "...", "evidence": [1, 2]}]}"""

_SUMMARY_SYSTEM = """你在为一位开发者写协作画像。输入是已经提炼好的结论，每行：`[kind → dest] 结论（次数 N / 项目 M）依据 #编号...`。

写 3~6 条总结，概括其协作风格与最重要的规则；每条一句中文，evidence 只能引用输入中出现的候选编号。

只输出 JSON：{"summary": [{"statement": "...", "evidence": [1, 2]}]}"""


def load_candidates(path: Path) -> tuple[list[Candidate], str]:
    """Load candidates.json written by mine; returns candidates and cluster backend."""
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run mine first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = [Candidate.from_dict(item) for item in payload["candidates"]]
    return candidates, str(payload["summary"].get("cluster_backend", "tfidf"))


def candidate_line(candidate: Candidate) -> str:
    """One compact prompt line per candidate; only patterns, variants and stats."""
    variants = "; ".join(f"{' '.join(v.text.split())} ×{v.count}" for v in candidate.variants)
    label = " ".join(candidate.label.split())
    return f"#{candidate.number} [{candidate.kind}] 次数 {candidate.count} 项目 {candidate.project_count} | {label} | 变体: {variants}"


def _stats(evidence: list[int], by_number: dict[int, Candidate]) -> tuple[int, int]:
    members = [by_number[n] for n in evidence]
    projects = {key for c in members for key in c.project_keys}
    return sum(c.count for c in members), len(projects)


def _valid_evidence(raw: Any, allowed: set[int]) -> list[int]:
    if not isinstance(raw, list):
        return []
    numbers = [item for item in raw if isinstance(item, int) and not isinstance(item, bool)]
    return sorted({n for n in numbers if n in allowed})


def _parse_conclusions(
    payload: dict[str, Any], allowed: set[int], by_number: dict[int, Candidate]
) -> tuple[list[Conclusion], int]:
    items = payload.get("conclusions")
    if not isinstance(items, list):
        raise LlmError("reply has no 'conclusions' array")
    kept: list[Conclusion] = []
    dropped = 0
    for item in items:
        if not isinstance(item, dict):
            dropped += 1
            continue
        statement = str(item.get("statement", "")).strip()
        evidence = _valid_evidence(item.get("evidence"), allowed)
        kind = item.get("kind") if item.get("kind") in KINDS else "style"
        dest = item.get("dest") if item.get("dest") in DESTS else "notes"
        if not statement or not evidence:
            dropped += 1
            continue
        count, project_count = _stats(evidence, by_number)
        kept.append(Conclusion(statement, str(kind), str(dest), evidence, count, project_count))
    return kept, dropped


def synthesize_conclusions(candidates: list[Candidate], chat: ChatFn) -> tuple[list[Conclusion], list[Conclusion], int]:
    """Return (summary, conclusions, dropped_count) for the given candidates."""
    by_number = {c.number: c for c in candidates}
    conclusions: list[Conclusion] = []
    dropped = 0
    for group in _GROUPS:
        members = [c for c in candidates if review_section(c) in group.sections]
        if not members:
            continue
        user = f"本组：{group.title}\n\n" + "\n".join(candidate_line(c) for c in members)
        found, lost = _parse_conclusions(parse_json_reply(chat(_SYSTEM, user)), {c.number for c in members}, by_number)
        conclusions += found
        dropped += lost

    conclusions.sort(key=lambda c: (DESTS.index(c.dest), -c.project_count, -c.count))
    if not conclusions:
        return [], conclusions, dropped

    cited = {n for c in conclusions for n in c.evidence}
    user = "\n".join(
        f"[{c.kind} → {c.dest}] {c.statement}（次数 {c.count} / 项目 {c.project_count}）依据 "
        + " ".join(f"#{n}" for n in c.evidence)
        for c in conclusions
    )
    payload = parse_json_reply(chat(_SUMMARY_SYSTEM, user))
    items = payload.get("summary")
    if not isinstance(items, list):
        raise LlmError("reply has no 'summary' array")
    summary: list[Conclusion] = []
    for item in items:
        evidence = _valid_evidence(item.get("evidence") if isinstance(item, dict) else None, cited)
        statement = str(item.get("statement", "")).strip() if isinstance(item, dict) else ""
        if not statement or not evidence:
            dropped += 1
            continue
        count, project_count = _stats(evidence, by_number)
        summary.append(Conclusion(statement, "style", "notes", evidence, count, project_count))
    return summary, conclusions, dropped


def _evidence_text(conclusion: Conclusion) -> str:
    refs = " ".join(f"#{n}" for n in conclusion.evidence)
    return f"{refs}（簇合计 {conclusion.count} 次 / {conclusion.project_count} 项目）"


def render_conclusions_md(result: SynthesisResult) -> str:
    lines = [
        "# 结论",
        "",
        f"- 模型：{result.model}；聚类：{result.cluster_backend}；输入候选 {result.candidate_count}",
        "- 依据中的编号对应 candidates.md；「簇合计」是依据簇的全部发言数与项目数（本地计算），簇内可能含与结论无关的变体，不等于支持该结论的次数",
        "",
        "## 画像总结",
        "",
        *([f"- {c.statement} — {_evidence_text(c)}" for c in result.summary] or ["无"]),
        "",
    ]
    for dest in DESTS:
        rows = [c for c in result.conclusions if c.dest == dest]
        lines += [f"## {_DEST_TITLES[dest]}（{len(rows)}）", ""]
        lines += [f"- [{c.kind}] {c.statement} — {_evidence_text(c)}" for c in rows] or ["无"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_synthesis(out_dir: Path, chat: ChatFn, model: str) -> SynthesisResult:
    """Read candidates.json, synthesize conclusions, and write conclusions.md / .json."""
    candidates, backend = load_candidates(out_dir / "candidates.json")
    summary, conclusions, dropped = synthesize_conclusions(candidates, chat)
    result = SynthesisResult(
        model=model,
        cluster_backend=backend,
        candidate_count=len(candidates),
        summary=summary,
        conclusions=conclusions,
        dropped_count=dropped,
        conclusions_md_path=str(out_dir / CONCLUSIONS_MD),
        conclusions_json_path=str(out_dir / CONCLUSIONS_JSON),
    )
    with atomic_text_writer(out_dir / CONCLUSIONS_MD) as handle:
        handle.write(render_conclusions_md(result))
    with atomic_text_writer(out_dir / CONCLUSIONS_JSON) as handle:
        handle.write(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n")
    return result
