"""Unit tests for extract service filters and session parsing."""

import json
from pathlib import Path

from app.services.extract import (
    extract_sessions,
    is_confirm_utterance,
    is_slash_command,
    join_user_text,
    make_utterance_id,
    project_key_from_source,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sessions"


def test_join_user_text_concatenates_text_blocks() -> None:
    content = [
        {"type": "image", "data": "..."},
        {"type": "text", "text": "第一段"},
        {"type": "text", "text": "第二段"},
    ]
    assert join_user_text(content) == "第一段\n第二段"


def test_join_user_text_accepts_plain_string() -> None:
    assert join_user_text("纯字符串发言") == "纯字符串发言"


def test_join_user_text_empty_when_no_text_parts() -> None:
    assert join_user_text([{"type": "image", "data": "..."}]) == ""


def test_slash_command_filter_boundaries() -> None:
    assert is_slash_command("/resume")
    assert is_slash_command("/compact now")
    assert is_slash_command("/session")
    assert not is_slash_command("/Users/jellyfish/code/demo 这个目录怎么处理")
    assert not is_slash_command("/api/v1/novels 参数")
    assert not is_slash_command("先别改代码，只讨论方案")


def test_confirm_filter_keeps_correction_phrases() -> None:
    assert is_confirm_utterance("好")
    assert is_confirm_utterance("ok")
    assert is_confirm_utterance("继续")
    assert is_confirm_utterance("OK")
    assert not is_confirm_utterance("先别改代码，只讨论方案")
    assert not is_confirm_utterance("帮我提交")


def test_project_key_from_source_uses_session_subdir() -> None:
    rel = Path("--Users-jellyfish-code-demo-proj--/2026-06-09T01-48-10-419Z_sess-demo.jsonl")
    assert project_key_from_source(rel) == "--Users-jellyfish-code-demo-proj--"


def test_utterance_id_is_stable() -> None:
    first = make_utterance_id("sess-demo", "e1")
    second = make_utterance_id("sess-demo", "e1")
    other = make_utterance_id("sess-demo", "e2")
    assert first == second
    assert first != other
    assert len(first) == 16


def test_extract_sessions_writes_filtered_utterances(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = extract_sessions(FIXTURES, out_dir)

    out_file = out_dir / "utterances.jsonl"
    assert out_file.is_file()
    assert result["utterance_count"] == 6
    assert result["session_file_count"] == 2
    assert result["skipped_slash"] == 3
    assert result["skipped_confirm"] == 3
    assert result["output_path"] == str(out_file)

    rows = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines()]
    texts = [row["text"] for row in rows]
    assert texts == [
        "第一段\n第二段",
        "先别改代码，只讨论方案",
        "/Users/jellyfish/code/demo 这个目录怎么处理",
        "看这张图",
        "纯字符串发言",
        "帮我提交",
    ]

    first = rows[0]
    assert first["session_id"] == "sess-demo"
    assert first["entry_id"] == "e1"
    assert first["cwd"] == "/Users/jellyfish/code/demo/proj"
    assert first["project_key"] == "--Users-jellyfish-code-demo-proj--"
    assert first["char_len"] == len("第一段\n第二段")
    assert first["source_file"].endswith("sess-demo.jsonl")
    assert first["utterance_id"] == make_utterance_id("sess-demo", "e1")

    other = rows[-1]
    assert other["session_id"] == "sess-other"
    assert other["project_key"] == "--Users-jellyfish-code-other--"
