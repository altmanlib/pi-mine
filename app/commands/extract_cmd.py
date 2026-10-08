"""extract command: sessions → utterances."""

from pathlib import Path

import click

from app.options import json_option, out_dir_option, sessions_dir_option
from app.output import output_json, print_lines
from app.services.extract import extract_sessions, extract_summary_lines


@click.command("extract")
@sessions_dir_option
@out_dir_option
@json_option
def extract_cmd(sessions_dir: Path, out_dir: Path, as_json: bool) -> None:
    """Extract user utterances from session JSONL files."""
    if not sessions_dir.is_dir():
        raise click.ClickException(f"sessions directory not found: {sessions_dir}")

    result = extract_sessions(sessions_dir, out_dir)
    if as_json:
        output_json(result)
    else:
        print_lines(extract_summary_lines(result))
