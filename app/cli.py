"""Click root entry for pi-mine."""

import click

from app import __version__
from app.commands.extract_cmd import extract_cmd
from app.commands.mine_cmd import mine_cmd
from app.commands.status_cmd import status_cmd
from app.commands.synthesize_cmd import synthesize_cmd


@click.group()
@click.version_option(__version__, prog_name="pi-mine")
def cli() -> None:
    """Mine user phrases and constraints from Pi coding-agent sessions."""


cli.add_command(extract_cmd)
cli.add_command(mine_cmd)
cli.add_command(status_cmd)
cli.add_command(synthesize_cmd)


if __name__ == "__main__":
    cli()
