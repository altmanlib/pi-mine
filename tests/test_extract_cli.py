"""CLI wiring tests for extract."""

import json
from pathlib import Path

from click.testing import CliRunner

from app.cli import cli

FIXTURES = Path(__file__).parent / "fixtures" / "sessions"


def test_extract_cli_human(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["extract", "--sessions-dir", str(FIXTURES), "--out", str(out_dir)],
    )
    assert result.exit_code == 0, result.output
    assert "utterance_count: 6" in result.output
    assert (out_dir / "utterances.jsonl").is_file()


def test_extract_cli_json(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "extract",
            "--sessions-dir",
            str(FIXTURES),
            "--out",
            str(out_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["utterance_count"] == 6
    assert payload["session_file_count"] == 2
