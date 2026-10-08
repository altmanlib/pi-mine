"""Shared Click options and path helpers."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click


def resolve_user_path(value: str | Path) -> Path:
    """Expand ``~`` and resolve to an absolute path."""
    return Path(value).expanduser().resolve()


def _path_option(value: str | None) -> Path | None:
    if value is None:
        return None
    return resolve_user_path(value)


def json_option[F: Callable[..., Any]](f: F) -> F:
    """Attach a ``--json`` flag usable on leaf commands."""
    return click.option(
        "--json",
        "as_json",
        is_flag=True,
        default=False,
        help="Output as JSON",
    )(f)


def sessions_dir_option[F: Callable[..., Any]](f: F) -> F:
    return click.option(
        "--sessions-dir",
        type=click.Path(file_okay=False, path_type=str),
        default="~/.pi/agent/sessions",
        show_default=True,
        callback=lambda _ctx, _param, value: _path_option(value),
        help="Pi sessions root directory",
    )(f)


def out_dir_option[F: Callable[..., Any]](f: F) -> F:
    return click.option(
        "--out",
        "out_dir",
        type=click.Path(file_okay=False, path_type=str),
        default="out",
        show_default=True,
        callback=lambda _ctx, _param, value: _path_option(value),
        help="Output directory (repo-local by default)",
    )(f)
