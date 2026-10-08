"""status command: show extract/mine output presence."""

from pathlib import Path

import click

from app.options import json_option, out_dir_option
from app.output import output_json, print_lines
from app.services.status import collect_status, status_lines


@click.command("status")
@out_dir_option
@json_option
def status_cmd(out_dir: Path, as_json: bool) -> None:
    """Show whether extract/mine outputs exist."""
    payload = collect_status(out_dir)
    if as_json:
        output_json(payload)
        return
    print_lines(status_lines(payload))
