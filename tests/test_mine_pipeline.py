"""Tests for cluster, rank, render and the mine command."""

import json
from pathlib import Path

from click.testing import CliRunner

from app.cli import cli
from app.models import Phrase
from app.services.cluster import cluster_phrases
from app.services.extract import extract_sessions
from app.services.normalize import is_correction_key, normalize_key
from app.services.rank import classify_kind, rank_clusters
from app.services.render import display_cwd

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
        phrase("push", count=3, projects=("a",), first="2026-01-01T00:00:00Z", last="2026-03-01T00:00:00Z"),
        phrase("发版", count=3, projects=("a",)),
        phrase("hi", count=2),
    ]
    clusters = [[0], [1], [2], [3]]
    candidates = rank_clusters(phrases, clusters, min_count=3, min_projects=3)
    assert [(c.label, c.confidence, c.suggested_dest) for c in candidates] == [
        ("commit", "strong", "skill"),
        ("push", "strong", "skill"),
        ("发版", "medium", "prompt"),
    ]
    assert candidates[1].day_span == 59
    assert candidates[0].project_count == 3


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
    assert summary["candidate_count"] == summary["phrase_count"] - 0 or summary["candidate_count"] >= 1

    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert len(payload["candidates"]) == summary["candidate_count"]
    assert "# Candidates" in (tmp_path / "candidates.md").read_text(encoding="utf-8")
    persona = (tmp_path / "persona.md").read_text(encoding="utf-8")
    assert "## Project distribution" in persona
    assert "| ~/code/demo/proj |" in persona


def test_mine_cli_requires_extract_first(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["mine", "--out", str(tmp_path)])
    assert result.exit_code != 0
    assert "run extract first" in result.output
