"""extract command: sessions → utterances."""

from pathlib import Path

import click

from app.models import ExtractResult
from app.options import json_option, out_dir_option, sessions_dir_option
from app.output import output_json, print_lines
from app.services.extract import extract_sessions


def _summary_lines(result: ExtractResult) -> list[str]:
    return [
        f"sessions_dir: {result.sessions_dir}",
        f"output_path: {result.output_path}",
        f"session_file_count: {result.session_file_count}",
        f"utterance_count: {result.utterance_count}",
        f"project_count: {result.project_count}",
        f"skipped_slash: {result.skipped_slash}",
        f"skipped_confirm: {result.skipped_confirm}",
        f"skipped_empty: {result.skipped_empty}",
        f"skipped_no_session: {result.skipped_no_session}",
        f"skipped_malformed: {result.skipped_malformed}",
    ]


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
        output_json(result.to_dict())
    else:
        print_lines(_summary_lines(result))
