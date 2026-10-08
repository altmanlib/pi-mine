from app.services.status import collect_status, status_lines


def test_collect_status_missing(tmp_path) -> None:
    payload = collect_status(tmp_path)
    assert payload["out_dir_exists"] is True
    assert payload["files"]["utterances"]["exists"] is False
    assert "utterances: no" in "\n".join(status_lines(payload))


def test_collect_status_with_file(tmp_path) -> None:
    path = tmp_path / "utterances.jsonl"
    path.write_text("x\n", encoding="utf-8")
    payload = collect_status(tmp_path)
    assert payload["files"]["utterances"]["exists"] is True
    assert payload["files"]["utterances"]["size"] == 2
