"""mine command: utterances → candidates + persona."""

from pathlib import Path

import click

from app.models import MineSummary
from app.options import json_option, out_dir_option
from app.output import output_json, print_lines
from app.services.mine import mine_utterances


def _summary_lines(summary: MineSummary) -> list[str]:
    return [
        f"out_dir: {summary.out_dir}",
        f"utterance_count: {summary.utterance_count}",
        f"fork_duplicate_count: {summary.fork_duplicate_count}",
        f"phrase_count: {summary.phrase_count}",
        f"cluster_count: {summary.cluster_count}",
        f"candidate_count: {summary.candidate_count}",
        f"strong_count: {summary.strong_count}",
        f"candidates_md: {summary.candidates_md_path}",
        f"candidates_json: {summary.candidates_json_path}",
        f"persona: {summary.persona_path}",
    ]


@click.command("mine")
@out_dir_option
@click.option("--min-count", type=click.IntRange(min=1), default=3, show_default=True, help="Minimum merged occurrences")
@click.option("--min-projects", type=click.IntRange(min=1), default=3, show_default=True, help="Project coverage for strong")
@json_option
def mine_cmd(out_dir: Path, min_count: int, min_projects: int, as_json: bool) -> None:
    """Cluster phrases and render candidates + persona."""
    try:
        summary = mine_utterances(out_dir, min_count, min_projects)
    except FileNotFoundError as error:
        raise click.ClickException(str(error)) from error
    if as_json:
        output_json(summary.to_dict())
    else:
        print_lines(_summary_lines(summary))
