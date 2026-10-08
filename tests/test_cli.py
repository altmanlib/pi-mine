from click.testing import CliRunner

from app.cli import cli


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_status_human(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--out", str(tmp_path)])
    assert result.exit_code == 0
    assert f"out_dir: {tmp_path.resolve()}" in result.output
    assert "utterances: no" in result.output


def test_status_json(tmp_path) -> None:
    out_file = tmp_path / "utterances.jsonl"
    out_file.write_text("{}\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--out", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"exists": true' in result.output
    assert "utterances.jsonl" in result.output
