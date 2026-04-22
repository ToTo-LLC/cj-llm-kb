"""Typer root. Subcommands land in commands/ (Task 20)."""

from __future__ import annotations

import typer

from brain_cli import __version__
from brain_cli.commands.chat import chat
from brain_cli.commands.doctor import doctor
from brain_cli.commands.mcp import mcp_app
from brain_cli.commands.patches import patches_app
from brain_cli.commands.start import start
from brain_cli.commands.status import status
from brain_cli.commands.stop import stop

app = typer.Typer(
    name="brain",
    help="brain — local LLM-maintained personal knowledge base",
    no_args_is_help=True,
    add_completion=False,
)

app.command()(chat)
# Plan 08 Task 3 — supervisor verbs.
app.command()(start)
app.command()(stop)
app.command()(status)
# Plan 08 Task 4 — diagnostic.
app.command()(doctor)
app.add_typer(patches_app, name="patches")
app.add_typer(mcp_app, name="mcp")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"brain {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """brain CLI root."""
