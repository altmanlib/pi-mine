"""status command: show extract/mine output presence."""

from pathlib import Path
from typing import Any

import click

from app.options import json_option, out_dir_option
from app.output import output_json, print_lines
from app.services.status import TRACKED_FILES, collect_status


def _status_lines(payload: dict[str, Any]) -> list[str]:
    """Render a compact human summary."""
    lines = [
        f"out_dir: {payload['out_dir']}",
        f"out_dir_exists: {payload['out_dir_exists']}",
    ]
    files = payload["files"]
    for key, _name in TRACKED_FILES:
        item = files[key]
        mark = "yes" if item["exists"] else "no"
        size = item["size"]
        lines.append(f"{key}: {mark} ({size} bytes)")
    return lines


@click.command("status")
@out_dir_option
@json_option
def status_cmd(out_dir: Path, as_json: bool) -> None:
    """Show whether extract/mine outputs exist."""
    payload = collect_status(out_dir)
    if as_json:
        output_json(payload)
        return
    print_lines(_status_lines(payload))
