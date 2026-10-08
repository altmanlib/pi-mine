"""mine command: utterances → candidates + persona."""

from pathlib import Path

import click

from app.options import json_option, out_dir_option


@click.command("mine")
@out_dir_option
@click.option("--min-count", type=int, default=3, show_default=True)
@click.option("--min-projects", type=int, default=3, show_default=True)
@json_option
def mine_cmd(out_dir: Path, min_count: int, min_projects: int, as_json: bool) -> None:
    """Cluster phrases and render candidates + persona."""
    _ = (out_dir, min_count, min_projects, as_json)
    raise click.ClickException("mine is not implemented yet; see docs/design/2026-10-08-01-pipeline.md")
