"""extract command: sessions → utterances."""

from pathlib import Path

import click

from app.options import json_option, out_dir_option, sessions_dir_option


@click.command("extract")
@sessions_dir_option
@out_dir_option
@json_option
def extract_cmd(sessions_dir: Path, out_dir: Path, as_json: bool) -> None:
    """Extract user utterances from session JSONL files."""
    _ = (sessions_dir, out_dir, as_json)
    raise click.ClickException("extract is not implemented yet; see docs/design/2026-10-08-01-pipeline.md")
