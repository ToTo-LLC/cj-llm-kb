"""``brain start`` — supervise a single brain_api uvicorn process.

Flow (Plan 08 Task 3):

1. Resolve install + vault dirs from env / platform defaults.
2. Probe pid file: already-running short-circuit vs stale cleanup.
3. Probe ports 4317..4330 → write chosen port to .brain/run/brain.port.
4. Spawn uvicorn with the correct env. Write pid file.
5. Poll /healthz (10s budget).
6. Open the browser + print the URL.
7. Spawn a daemon thread that checks GitHub for a newer release and
   prints a one-line nudge if one exists (Plan 09 Task 4 / Q2a).
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import typer

from brain_cli.runtime import browser, pidfile, portprobe, release, supervisor


def _resolve_install_dir() -> Path:
    """Resolve the brain install directory.

    Priority:
      1. ``BRAIN_INSTALL_DIR`` env var (explicit override; install script sets it).
      2. Platform default: ``~/Applications/brain/`` on Mac, ``%LOCALAPPDATA%\\brain\\``
         on Windows, ``~/.local/share/brain/`` on Linux.
      3. Dev fallback: the repo root (detected by a nearby ``pyproject.toml``
         with ``brain`` or workspace members).

    We accept a dir even if it doesn't fully exist yet — the supervisor
    only creates the log dir under ``<vault>/.brain/``, not the install
    dir (which is owned by ``scripts/install.sh``).
    """
    env = os.environ.get("BRAIN_INSTALL_DIR")
    if env:
        return Path(env)

    if sys.platform == "darwin":
        return Path.home() / "Applications" / "brain"
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "brain"
        # Fallback for exotic Windows where LOCALAPPDATA is unset.
        return Path.home() / "AppData" / "Local" / "brain"

    # Linux + unknown POSIX fallback.
    return Path.home() / ".local" / "share" / "brain"


def _resolve_vault_root() -> Path:
    """Vault root: env var override, else ``~/Documents/brain/``."""
    env = os.environ.get("BRAIN_VAULT_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "brain"


def _resolve_web_out_dir(install_dir: Path) -> Path:
    """Pick the first existing candidate for the Next.js static-export dir.

    Tried in order:
      1. ``<install>/web/out``          — packaged install layout
      2. ``<install>/apps/brain_web/out`` — dev / repo-root layout

    Returns the FIRST candidate that contains ``index.html``; if neither
    exists, returns candidate #1 and lets brain_api surface the error
    at startup (keeps the "missing UI bundle" error message on one side
    of the boundary — brain_api.static_ui — not duplicated here).
    """
    candidates = [
        install_dir / "web" / "out",
        install_dir / "apps" / "brain_web" / "out",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return candidates[0]


def start(
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root directory (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
) -> None:
    """Start the brain daemon: spawn brain_api, wait for /healthz, open the browser."""
    install_dir = _resolve_install_dir()
    vault_root = vault or _resolve_vault_root()

    run_dir = vault_root / ".brain" / "run"
    log_dir = vault_root / ".brain" / "logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    pid_file = run_dir / "brain.pid"
    port_file = run_dir / "brain.port"
    log_file = log_dir / "brain-api.log"

    # Already-running short-circuit.
    existing_pid = pidfile.read_pid(pid_file)
    if existing_pid is not None:
        if pidfile.is_alive(existing_pid) and pidfile.is_brain_api(existing_pid):
            existing_port = _read_port(port_file)
            url = (
                f"http://localhost:{existing_port}/"
                if existing_port is not None
                else "http://localhost:<unknown-port>/"
            )
            typer.echo(f"brain already running at {url}")
            raise typer.Exit(code=0)
        # Stale: cleanup + continue.
        pidfile.delete_pid(pid_file)
        if port_file.exists():
            port_file.unlink()

    # Port probe.
    try:
        port = portprobe.find_free_port()
    except portprobe.NoFreePortError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    port_file.write_text(f"{port}\n", encoding="utf-8")

    web_out_dir = _resolve_web_out_dir(install_dir)

    # Spawn.
    try:
        proc = supervisor.start_brain_api(
            port=port,
            install_dir=install_dir,
            vault_root=vault_root,
            web_out_dir=web_out_dir,
            log_path=log_file,
        )
    except FileNotFoundError as exc:
        # ``uv`` not on PATH — surface a plain-English next-action.
        typer.echo(
            "error: `uv` not found on PATH. Install uv first "
            "(https://astral.sh/uv) or run `brain doctor`.",
            err=True,
        )
        if port_file.exists():
            port_file.unlink()
        raise typer.Exit(code=1) from exc

    pidfile.write_pid(pid_file, proc.pid)

    # Healthz poll.
    if not supervisor.wait_for_healthz(port=port, timeout_s=10.0):
        # Clean up so the next `brain start` doesn't think we're running.
        supervisor.stop_brain_api(proc.pid)
        pidfile.delete_pid(pid_file)
        if port_file.exists():
            port_file.unlink()
        typer.echo(
            f"error: brain_api did not become healthy within 10s. Check {log_file} for details.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Browser + success line.
    url = f"http://localhost:{port}/"
    browser.open_browser(url)
    typer.echo(f"brain running at {url}")

    # Non-blocking update-check nudge (Plan 09 Task 4 / Q2a). Daemon so
    # it can't hold the process open; short timeout so a slow network
    # can't stall anything; broad try/except so a failing check never
    # escapes into ``brain start``'s control flow.
    threading.Thread(target=_update_check_nudge, daemon=True).start()


def _read_port(port_file: Path) -> int | None:
    if not port_file.exists():
        return None
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _read_current_version(install_dir: Path) -> str:
    """Read the current brain version from ``<install>/VERSION``.

    Mirrors the upgrade command's resolver. Priority:
      1. ``<install>/VERSION`` (written by install.sh / install.ps1).
      2. ``brain_cli.__version__`` (module-level fallback).

    Returns ``"0.0.0"`` as a last-ditch sentinel so ``check_latest_release``
    always has a string to compare against — the check will then always
    report a newer version, which is the safest failure mode for a
    nudge (the user sees a suggestion, not a crash).
    """
    version_file = install_dir / "VERSION"
    if version_file.exists():
        try:
            raw = version_file.read_text(encoding="utf-8").strip()
            if raw:
                return raw.lstrip("v")
        except OSError:
            pass
    try:
        from brain_cli import __version__ as cli_version

        return cli_version
    except ImportError:  # pragma: no cover — brain_cli is the host package
        return "0.0.0"


def _update_check_nudge() -> None:
    """Background-thread entry point: check GitHub, print a nudge if newer.

    Hard safety rails:

    * Opt-out via ``BRAIN_NO_UPDATE_CHECK=1`` is enforced BEFORE any
      imports or network activity. ``check_latest_release`` itself also
      honors the env var, but we short-circuit here so the test-visible
      contract ("no call under opt-out") holds for any future wiring.
    * All exceptions are swallowed. Network timeouts, DNS failures,
      malformed JSON, GitHub rate-limits — none of them may escape this
      thread back into the ``brain start`` process.
    * The 3-second timeout keeps the thread bounded; the host process
      never waits for it (it's a daemon) but we still don't want the
      thread lingering.
    """
    if os.environ.get("BRAIN_NO_UPDATE_CHECK") == "1":
        return

    try:
        install_dir = _resolve_install_dir()
        current = _read_current_version(install_dir)
        info = release.check_latest_release(current, timeout_s=3)
        if info is None:
            return
        # ``current`` was already ``lstrip("v")``-ed by the reader; strip
        # the tag_name defensively so the printed "v{current} → v{latest}"
        # never ends up with a double-v.
        latest_clean = info.tag_name.lstrip("v") if info.tag_name else info.version
        typer.echo(
            f"A newer version is available: v{current} -> v{latest_clean}. "
            "Run 'brain upgrade' to update."
        )
    except Exception:
        # Silent failure mode: a nudge is a nice-to-have. Never crash
        # the host process, never print a traceback, never surface a
        # "couldn't check for updates" line — that would be noisier
        # than just staying quiet.
        return
