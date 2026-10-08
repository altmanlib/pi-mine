"""Unit tests for normalization and near-duplicate merging."""

from pathlib import Path

from app.models import Utterance
from app.services.extract import extract_sessions, read_utterances
from app.services.normalize import (
    is_confirm_utterance,
    is_correction_key,
    match_key,
    normalize_key,
    normalize_utterances,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sessions"


def make(uid: str, text: str, *, project: str = "p1", ts: str = "2026-06-01T00:00:00Z", session: str = "s1") -> Utterance:
    return Utterance(
        utterance_id=uid,
        session_id=session,
        entry_id=uid,
        timestamp=ts,
        cwd="/x",
        project_key=project,
        text=text,
        char_len=len(text),
        source_file="f.jsonl",
    )


def test_normalize_key_folds_case_width_whitespace_and_edges() -> None:
    assert normalize_key("  Git   COMMIT！ ") == "git commit"
    assert normalize_key("ＯＫ。") == "ok"
    assert normalize_key("…先别改代码，只讨论方案。") == "先别改代码,只讨论方案"
    assert normalize_key("！？") == ""


def test_confirm_uses_normalized_key() -> None:
    assert is_confirm_utterance("好的。")
    assert is_confirm_utterance("OK!")
    assert not is_confirm_utterance("执行")
    assert not is_confirm_utterance("好的，帮我提交")


def test_correction_markers() -> None:
    assert is_correction_key(normalize_key("先别改代码，只讨论方案"))
    assert is_correction_key(normalize_key("Don't touch it"))
    assert not is_correction_key(normalize_key("帮我提交"))


def test_exact_key_merge_picks_most_frequent_text() -> None:
    rows = [
        make("1", "Commit", ts="2026-06-01T00:00:01Z"),
        make("2", "commit.", ts="2026-06-02T00:00:00Z", project="p2"),
        make("3", "commit.", ts="2026-06-03T00:00:00Z", project="p3"),
    ]
    result = normalize_utterances(rows)
    assert len(result.phrases) == 1
    phrase = result.phrases[0]
    assert phrase.text == "commit."
    assert phrase.count == 3
    assert phrase.project_keys == ["p1", "p2", "p3"]
    assert phrase.first_timestamp == "2026-06-01T00:00:01Z"
    assert phrase.last_timestamp == "2026-06-03T00:00:00Z"
    assert phrase.utterance_ids == ["1", "2", "3"]


def test_fuzzy_merge_near_duplicates_but_not_distinct_instructions() -> None:
    rows = [
        make("1", "请先别改代码，只讨论方案，不要动文件"),
        make("2", "请先别改代码，只讨论方案，不要动文件吧"),
        make("3", "开始修复"),
        make("4", "开始执行"),
    ]
    result = normalize_utterances(rows)
    counts = sorted(p.count for p in result.phrases)
    assert counts == [1, 1, 2]
    merged = next(p for p in result.phrases if p.count == 2)
    assert merged.is_correction


def test_fork_duplicates_dropped() -> None:
    rows = [
        make("1", "同一句话", session="s1", ts="2026-06-01T00:00:00Z"),
        make("2", "同一句话", session="s2", ts="2026-06-01T00:00:00Z"),
        make("3", "同一句话", session="s3", ts="2026-06-02T00:00:00Z"),
    ]
    result = normalize_utterances(rows)
    assert result.input_count == 3
    assert result.fork_duplicate_count == 1
    assert result.phrases[0].count == 2


def test_blank_keys_are_skipped_and_order_is_by_count() -> None:
    rows = [make("1", "！！"), make("2", "a b c d"), make("3", "x y z w"), make("4", "x y z w", ts="2026-06-02T00:00:00Z")]
    result = normalize_utterances(rows)
    assert [p.norm_key for p in result.phrases] == ["x y z w", "a b c d"]


def test_normalize_from_extracted_fixture(tmp_path: Path) -> None:
    extract_sessions(FIXTURES, tmp_path)
    rows = read_utterances(tmp_path / "utterances.jsonl")
    result = normalize_utterances(rows)
    assert result.input_count == 6
    assert sum(p.count for p in result.phrases) == 6


def test_match_key_masks_paths_and_numbers_but_keeps_bare_ones() -> None:
    assert match_key("docs/plan/a.md 执行此方案") == match_key("docs/plans/b.md 执行此方案")
    assert match_key("docs/plan/a.md 执行此方案") != match_key("docs/plan/a.md 审查这个方案")
    assert match_key("read issue #20") == match_key("read issue #2")
    assert match_key("docs/plan/a.md") == "docs/plan/a.md"
    assert match_key("1") == "1"


def test_parameterized_phrase_merges_and_distinct_instructions_do_not() -> None:
    rows = [
        make("1", "docs/plan/2026-07-30-a.md 执行此方案"),
        make("2", "docs/plan/2026-07-31-b.md 执行此方案"),
        make("3", "docs/plan/2026-07-30-a.md 审查这个方案"),
        make("4", "1"),
        make("5", "2"),
    ]
    result = normalize_utterances(rows)
    assert sorted(p.count for p in result.phrases) == [1, 1, 1, 2]
