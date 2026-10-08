"""Tests for LLM synthesis: evidence validation, local stats, rendering and caching."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from app.cli import cli
from app.models import Candidate, Variant
from app.services.llm import LlmError, cached_chat, parse_json_reply
from app.services.synthesize import candidate_line, run_synthesis, synthesize_conclusions


def candidate(number: int, label: str, kind: str, count: int, projects: list[str], confidence: str = "strong") -> Candidate:
    return Candidate(
        number=number,
        candidate_id=f"id{number}",
        label=label,
        count=count,
        project_count=len(projects),
        day_span=10,
        kind=kind,
        suggested_dest="AGENTS",
        confidence=confidence,
        variant_count=1,
        variants=[Variant(text=label, count=count)],
        project_keys=projects,
    )


CANDIDATES = [
    candidate(1, "不需要每次都 cd", "constraint", 6, ["a", "b"]),
    candidate(2, "不要每次都 cd xxx", "constraint", 2, ["b", "c"]),
    candidate(3, "commit", "workflow", 50, ["a", "b", "c"]),
    candidate(4, "hi there", "other", 3, ["a"]),
]


class ScriptedChat:
    """Return canned replies keyed by the group title found in the user prompt."""

    def __init__(self, replies: dict[str, dict]) -> None:
        self.replies = replies
        self.users: list[str] = []

    def __call__(self, system: str, user: str) -> str:
        self.users.append(user)
        for marker, reply in self.replies.items():
            if marker in user:
                return json.dumps(reply, ensure_ascii=False)
        return json.dumps({"conclusions": []})


def scripted() -> ScriptedChat:
    return ScriptedChat(
        {
            "本组：约束": {
                "conclusions": [
                    # Numbers 1 and 2 are valid; 3 belongs to another group and 99 does not exist.
                    {"statement": "执行命令前不要每次都 cd", "kind": "constraint", "dest": "AGENTS", "evidence": [1, 2, 3, 99]},
                    {"statement": "无依据的结论", "kind": "constraint", "dest": "AGENTS", "evidence": [99]},
                ]
            },
            "本组：工作流": {
                "conclusions": [{"statement": "用 commit 收尾", "kind": "workflow", "dest": "bogus", "evidence": [3]}]
            },
            "[constraint → AGENTS]": {"summary": [{"statement": "偏好少废话直接执行", "evidence": [1, 4]}]},
        }
    )


def test_synthesize_validates_evidence_and_computes_stats_locally() -> None:
    chat = scripted()
    summary, conclusions, dropped = synthesize_conclusions(CANDIDATES, chat)

    first = conclusions[0]
    assert first.statement == "执行命令前不要每次都 cd"
    assert first.evidence == [1, 2]
    assert (first.count, first.project_count) == (8, 3)

    workflow = next(c for c in conclusions if c.kind == "workflow")
    assert workflow.dest == "notes"  # unknown dest falls back
    assert dropped == 1

    # Summary may only cite candidates already cited by conclusions (4 was never cited).
    assert [s.evidence for s in summary] == [[1]]
    assert (summary[0].count, summary[0].project_count) == (6, 2)


def test_prompt_lines_carry_only_patterns_and_stats() -> None:
    line = candidate_line(CANDIDATES[0])
    assert line == "#1 [constraint] 次数 6 项目 2 | 不需要每次都 cd | 变体: 不需要每次都 cd ×6"
    chat = scripted()
    synthesize_conclusions(CANDIDATES, chat)
    assert not any("id1" in user or "a, b" in user for user in chat.users)


def test_parse_json_reply_handles_fences_and_errors() -> None:
    assert parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LlmError):
        parse_json_reply("not json")
    with pytest.raises(LlmError):
        parse_json_reply("[1]")


def test_cached_chat_reuses_replies(tmp_path: Path) -> None:
    calls: list[str] = []

    def chat(system: str, user: str) -> str:
        calls.append(user)
        return '{"ok": true}'

    wrapped = cached_chat(chat, tmp_path / "cache", "m")
    assert wrapped("s", "u") == wrapped("s", "u")
    assert calls == ["u"]
    wrapped("s", "other")
    assert calls == ["u", "other"]


def test_run_synthesis_writes_outputs(tmp_path: Path) -> None:
    payload = {"summary": {"cluster_backend": "embedding"}, "candidates": [c.to_dict() for c in CANDIDATES]}
    (tmp_path / "candidates.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = run_synthesis(tmp_path, scripted(), "test-model")
    assert result.cluster_backend == "embedding"
    text = (tmp_path / "conclusions.md").read_text(encoding="utf-8")
    assert "## 写入 AGENTS 的规则（1）" in text
    assert "- [constraint] 执行命令前不要每次都 cd — #1 #2（簇合计 8 次 / 3 项目）" in text
    assert json.loads((tmp_path / "conclusions.json").read_text(encoding="utf-8"))["model"] == "test-model"


def test_synthesize_cli_requires_env_and_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIPROXYAPI_API_KEY", raising=False)
    result = CliRunner().invoke(cli, ["synthesize", "--out", str(tmp_path)])
    assert result.exit_code != 0
    assert "CLIPROXYAPI_API_KEY" in result.output

    monkeypatch.setenv("CLIPROXYAPI_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("CLIPROXYAPI_API_KEY", "k")
    result = CliRunner().invoke(cli, ["synthesize", "--out", str(tmp_path)])
    assert result.exit_code != 0
    assert "run mine first" in result.output
