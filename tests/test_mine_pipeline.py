"""Tests for cluster, rank, render and the mine command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from app.cli import cli
from app.models import MineSummary, Phrase
from app.services.cluster import cluster_phrases
from app.services.extract import extract_sessions
from app.services.mine import mine_utterances
from app.services.normalize import is_correction_key, mask_params, normalize_key
from app.services.rank import classify_kind, display_label, rank_clusters
from app.services.render import display_cwd, render_candidates_md

FIXTURES = Path(__file__).parent / "fixtures" / "sessions"


def phrase(
    text: str,
    count: int = 1,
    projects: tuple[str, ...] = ("p1",),
    first: str = "2026-06-01T00:00:00Z",
    last: str = "2026-06-01T00:00:00Z",
) -> Phrase:
    key = normalize_key(text)
    return Phrase(
        phrase_id=f"id-{abs(hash(text)) % 10**6}",
        text=text,
        norm_key=key,
        count=count,
        project_keys=list(projects),
        first_timestamp=first,
        last_timestamp=last,
        is_correction=is_correction_key(key),
        utterance_ids=[],
    )


def test_cluster_groups_similar_phrases_around_highest_count_leader() -> None:
    phrases = [
        phrase("请审查这个方案是否合理", count=5),
        phrase("请审查这个方案是否可行", count=3),
        phrase("docker build 报错了", count=2),
    ]
    assert cluster_phrases(phrases) == [[0, 1], [2]]
    assert cluster_phrases([]) == []


def test_classify_kind_rules() -> None:
    assert classify_kind(phrase("先别改代码，只讨论方案")) == "constraint"
    assert classify_kind(phrase("use gh to read the repo")) == "tooling"
    assert classify_kind(phrase("commit")) == "workflow"
    assert classify_kind(phrase("使用 Asia/Shanghai")) == "preference"
    assert classify_kind(phrase("hi")) == "other"
    assert classify_kind(phrase('<skill name="x">' + "a" * 10 + "</skill>")) == "template"
    assert classify_kind(phrase("a" * 250)) == "template"


def test_rank_filters_by_count_and_grades_confidence() -> None:
    phrases = [
        phrase("commit", count=4, projects=("a", "b", "c")),
        phrase("push", count=9, projects=("a",), first="2026-01-01T00:00:00Z", last="2026-05-01T00:00:00Z"),
        phrase("发版", count=3, projects=("a",)),
        phrase("hi", count=2),
    ]
    clusters = [[0], [1], [2], [3]]
    candidates = rank_clusters(phrases, clusters, min_count=3, min_projects=3)
    assert [(c.label, c.confidence, c.suggested_dest) for c in candidates] == [
        ("push", "strong", "skill"),
        ("commit", "strong", "skill"),
        ("发版", "medium", "prompt"),
    ]
    assert candidates[0].day_span == 120
    assert candidates[1].project_count == 3


def test_rank_skips_bare_paths() -> None:
    phrases = [phrase("/var/folders/zn/x/y.png", count=5), phrase("~/code/demo", count=5)]
    assert rank_clusters(phrases, [[0], [1]], min_count=3, min_projects=1) == []


def test_mask_params_collapses_versions_and_keeps_bare_values() -> None:
    assert mask_params("发版 0.7.0", "P", "N") == "发版 N"
    assert mask_params("@docs/plan/a.md 执行此方案", "P", "N") == "P 执行此方案"
    assert mask_params("docs/plan/a.md", "P", "N") == "docs/plan/a.md"


def test_display_label_masks_params_and_shortens_templates() -> None:
    assert display_label(phrase("@docs/plan/a.md 执行此方案"), "workflow") == "‹路径› 执行此方案"
    skill = phrase('<skill name="code-review" location="/x">' + "a" * 300)
    assert display_label(skill, "template") == "skill: code-review"
    prompt = phrase("# 执行：数据库备份\n\n- 步骤" + "a" * 300)
    assert display_label(prompt, "template") == "执行：数据库备份"


def test_rank_aggregates_variants_by_pattern() -> None:
    phrases = [
        phrase("read docs/a.md", count=4, projects=("a", "b", "c")),
        phrase("read docs/b.md", count=2),
        phrase("read this repo", count=1),
    ]
    [candidate] = rank_clusters(phrases, [[0, 1, 2]], min_count=3, min_projects=3)
    assert candidate.label == "read ‹路径›"
    assert candidate.variant_count == 2
    assert [(v.text, v.count) for v in candidate.variants] == [("read ‹路径›", 6), ("read this repo", 1)]


def test_render_candidates_md_groups_by_destination() -> None:
    phrases = [
        phrase("先别改代码", count=5, projects=("a", "b", "c")),
        phrase("commit", count=9, projects=("a", "b", "c")),
        phrase("发版", count=3),
    ]
    candidates = rank_clusters(phrases, [[0], [1], [2]], min_count=3, min_projects=3)
    summary = MineSummary(
        out_dir="out",
        min_count=3,
        min_projects=3,
        cluster_backend="tfidf",
        utterance_count=17,
        phrase_count=3,
        cluster_count=3,
        candidate_count=3,
        strong_count=2,
        fork_duplicate_count=0,
        candidates_md_path="",
        candidates_json_path="",
        persona_path="",
    )
    text = render_candidates_md(candidates, summary)
    constraint = text.index("## 约束与红线 → AGENTS（1）")
    workflow = text.index("## 工作流 → skill / prompt（1）")
    medium = text.index("## 附录 B：覆盖不足（medium）（1）")
    assert constraint < workflow < medium
    assert "| 1 | 先别改代码 | 5 | 3 |" in text
    assert "| 2 | commit | 9 | 3 |" in text
    assert "| 3 | 发版 | 3 | 1 | workflow | prompt |" in text


def test_display_cwd_replaces_home_prefix() -> None:
    assert display_cwd("/Users/someone/code/demo") == "~/code/demo"
    assert display_cwd("/srv/app") == "/srv/app"


def test_mine_cli_writes_outputs(tmp_path: Path) -> None:
    extract_sessions(FIXTURES, tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["mine", "--out", str(tmp_path), "--min-count", "1", "--json"])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["utterance_count"] == 6
    assert summary["candidate_count"] >= 1
    assert summary["cluster_backend"] == "tfidf"

    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert len(payload["candidates"]) == summary["candidate_count"]
    assert "# 资产候选" in (tmp_path / "candidates.md").read_text(encoding="utf-8")
    persona = (tmp_path / "persona.md").read_text(encoding="utf-8")
    assert "## Project distribution" in persona
    assert "| ~/code/demo/proj |" in persona


def test_mine_cli_requires_extract_first(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["mine", "--out", str(tmp_path)])
    assert result.exit_code != 0
    assert "run extract first" in result.output


def test_mine_with_embedding_fetch_uses_cached_vectors(tmp_path: Path) -> None:
    extract_sessions(FIXTURES, tmp_path)
    sent: list[str] = []

    def fetch(batch: list[str]) -> list[list[float]]:
        sent.extend(batch)
        # Every text gets the same direction, so all phrases collapse into one cluster.
        return [[1.0, 0.0] for _ in batch]

    summary = mine_utterances(tmp_path, min_count=1, min_projects=3, embedding_fetch=fetch)
    assert summary.cluster_backend == "embedding"
    assert summary.cluster_count == 1
    assert len(sent) == summary.phrase_count
    assert (tmp_path / "embeddings.npz").is_file()

    sent.clear()
    mine_utterances(tmp_path, min_count=1, min_projects=3, embedding_fetch=fetch)
    assert sent == []


def test_mine_cli_embedding_requires_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SILICONFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    extract_sessions(FIXTURES, tmp_path)
    result = CliRunner().invoke(cli, ["mine", "--out", str(tmp_path), "--embedding"])
    assert result.exit_code != 0
    assert "SILICONFLOW_API_KEY" in result.output
