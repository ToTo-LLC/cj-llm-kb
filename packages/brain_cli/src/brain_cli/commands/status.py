"""``brain status`` — report whether the brain daemon is running.

Human-readable by default. Use ``--json`` for scripting.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import psutil
import typer

from brain_cli.runtime import pidfile


def _resolve_vault_root() -> Path:
    env = os.environ.get("BRAIN_VAULT_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "brain"


def _format_uptime(seconds: float) -> str:
    """Render ``N.Ns`` into a compact ``HhMMmSSs`` form.

    Always omits zero units at the front: 5s, 1m05s, 1h02m03s.
    """
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _read_port(port_file: Path) -> int | None:
    if not port_file.exists():
        return None
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _get_uptime_seconds(pid: int) -> float | None:
    try:
        proc = psutil.Process(pid)
        return time.time() - proc.create_time()
    except Exception:
        # psutil restricted on some systems; uptime is best-effort.
        return None


def status(
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root directory (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a single-line JSON document for scripting.",
    ),
) -> None:
    """Print whether the brain daemon is running + pid + port + uptime."""
    vault_root = vault or _resolve_vault_root()
    run_dir = vault_root / ".brain" / "run"
    pid_file = run_dir / "brain.pid"
    port_file = run_dir / "brain.port"

    pid = pidfile.read_pid(pid_file)
    running = pid is not None and pidfile.is_alive(pid) and pidfile.is_brain_api(pid)

    if not running:
        if as_json:
            typer.echo(json.dumps({"running": False, "pid": None, "port": None, "url": None}))
        else:
            typer.echo("brain not running")
        raise typer.Exit(code=0)

    port = _read_port(port_file)
    url = f"http://localhost:{port}/" if port is not None else None
    uptime_s = _get_uptime_seconds(pid) if pid is not None else None

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "running": True,
                    "pid": pid,
                    "port": port,
                    "url": url,
                    "uptime_seconds": int(uptime_s) if uptime_s is not None else None,
                }
            )
        )
        raise typer.Exit(code=0)

    uptime_str = _format_uptime(uptime_s) if uptime_s is not None else "unknown"
    typer.echo(f"brain running · pid {pid} · {url} · uptime {uptime_str}")
