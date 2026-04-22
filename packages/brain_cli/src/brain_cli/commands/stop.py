"""``brain stop`` — gracefully terminate the brain_api daemon.

Idempotent: if no pid file exists or the process is already dead, we
print a polite "not running" message and exit 0. Always removes the pid
and port files so the next ``brain start`` starts fresh.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from brain_cli.runtime import pidfile, supervisor


def _resolve_vault_root() -> Path:
    env = os.environ.get("BRAIN_VAULT_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "brain"


def stop(
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root directory (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
) -> None:
    """Stop the brain daemon if running; always clean up state files."""
    vault_root = vault or _resolve_vault_root()
    run_dir = vault_root / ".brain" / "run"
    pid_file = run_dir / "brain.pid"
    port_file = run_dir / "brain.port"

    pid = pidfile.read_pid(pid_file)

    if pid is None or not pidfile.is_alive(pid):
        typer.echo("brain not running")
        # Still clean up any lingering files so the filesystem tells the truth.
        pidfile.delete_pid(pid_file)
        if port_file.exists():
            port_file.unlink()
        raise typer.Exit(code=0)

    supervisor.stop_brain_api(pid)
    pidfile.delete_pid(pid_file)
    if port_file.exists():
        port_file.unlink()
    typer.echo(f"brain stopped (pid {pid})")
