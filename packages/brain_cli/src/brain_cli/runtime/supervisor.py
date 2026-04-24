"""Uvicorn supervisor helpers.

Spawns ``uvicorn --factory brain_cli.runtime.backend_factory:build_app``
with the correct env so brain_api picks up the vault, web-out dir, and
port. We invoke uvicorn directly via ``sys.executable -m uvicorn`` —
brain_cli is always launched from a uv-managed venv (the install shim
runs ``uv run brain ...``), so ``sys.executable`` already points at a
Python with uvicorn installed. Going through the venv Python instead of
a nested ``uv run`` call drops one layer of indirection and avoids the
PATH trap: when brain_cli is itself spawned under ``uv run``, the child
process's PATH includes the venv's ``bin/`` but NOT ``~/.local/bin/``
where ``uv`` lives, so a bare ``["uv", ...]`` Popen would fail with
``FileNotFoundError``. Kill is psutil-backed so we don't have to branch
on POSIX signals vs Windows termination semantics. Health check uses
httpx against ``/healthz`` with a 200ms poll.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

# Log file rotation threshold. At 50MB we rename <log>.log → <log>.log.1 and
# start fresh. Simple + works the same on all platforms; fancy log rotators
# aren't worth the dependency surface.
_LOG_ROTATE_BYTES = 50 * 1024 * 1024

# psutil's wait timeout for graceful terminate. 5 seconds matches spec §9.
_TERMINATE_GRACE_S = 5.0

# Health probe cadence. 200ms is plenty responsive for a user-visible
# "brain starting…" experience without hammering the child while it's
# still bootstrapping SQLite + the config loader.
_HEALTHZ_POLL_INTERVAL_S = 0.2


def _rotate_log_if_oversized(log_path: Path) -> None:
    """If the log file exceeds the rotation threshold, move it to ``.1``."""
    try:
        if log_path.exists() and log_path.stat().st_size > _LOG_ROTATE_BYTES:
            rotated = log_path.with_suffix(log_path.suffix + ".1")
            # Replace any prior .1 (single-generation rotation; keeping
            # more generations is out of scope for Plan 08).
            if rotated.exists():
                rotated.unlink()
            log_path.rename(rotated)
    except OSError:
        # Rotation failures must not block ``brain start``; worst case
        # we just append to an oversized file.
        pass


def start_brain_api(
    *,
    port: int,
    install_dir: Path,
    vault_root: Path,
    web_out_dir: Path,
    log_path: Path,
) -> subprocess.Popen[bytes]:
    """Spawn ``python -m uvicorn --factory ...`` as a child process.

    Returns the ``Popen`` object (caller stores ``.pid`` in the PID file).
    Never uses ``shell=True``. Passes a scrubbed env with the BRAIN_*
    vars the factory expects.

    We use ``sys.executable`` (the venv's Python interpreter) rather
    than a nested ``uv run`` call. The parent Python process is already
    running inside the venv — either because the user ran ``uv run
    brain ...`` directly or because the install shim did. That means
    ``sys.executable`` resolves to the venv's Python which has
    ``uvicorn`` installed. Going through ``uv run`` adds zero value
    and fails when PATH doesn't include ``uv``'s install location
    (e.g. a child of ``uv run`` has the venv's ``bin/`` on PATH but
    NOT ``~/.local/bin/``).

    On Windows, we add ``CREATE_NEW_PROCESS_GROUP`` so Ctrl+C in the
    parent shell doesn't cascade into the child (matches Plan 08 spec).
    """
    _rotate_log_if_oversized(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["BRAIN_VAULT_ROOT"] = str(vault_root)
    env["BRAIN_WEB_OUT_DIR"] = str(web_out_dir)
    env["BRAIN_API_PORT"] = str(port)
    env["BRAIN_INSTALL_DIR"] = str(install_dir)
    # Pass through BRAIN_LLM_PROVIDER etc. if caller already set them (e.g.
    # e2e runs using FakeLLM). os.environ.copy() above already does this;
    # we're just not scrubbing it.

    cmd: list[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
        "brain_cli.runtime.backend_factory:build_app",
    ]

    # Open log file in append-binary mode; Popen takes ownership via the
    # fd, so we don't close it here — the child keeps it open for its
    # lifetime. Python will close the fd on Popen teardown.
    log_fh = log_path.open("ab")

    # Windows-only CREATE_NEW_PROCESS_GROUP so Ctrl+C in the parent shell
    # doesn't cascade to the child. Defaults to 0 (no flag) on POSIX.
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    return subprocess.Popen(
        cmd,
        env=env,
        shell=False,
        cwd=str(install_dir),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )


def stop_brain_api(pid: int) -> None:
    """Terminate the daemon at ``pid`` gracefully, escalating to kill on timeout.

    Idempotent: if the PID is already dead, returns without raising.
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    except Exception:
        # Other psutil internal errors — can't proceed, but don't raise
        # since the caller will clean up the PID file regardless.
        return

    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        return
    except Exception:
        return

    try:
        proc.wait(timeout=_TERMINATE_GRACE_S)
    except psutil.TimeoutExpired:
        # Graceful terminate didn't take — escalate.
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        except Exception:
            pass
    except psutil.NoSuchProcess:
        return


def wait_for_healthz(port: int, timeout_s: float = 10.0) -> bool:
    """Poll ``http://127.0.0.1:<port>/healthz`` until 200 or timeout.

    Returns True on first 200, False on timeout. Uses httpx for the
    cross-platform HTTP client (brain_api already depends on it
    transitively; brain_cli adds it directly for this probe).
    """
    url = f"http://127.0.0.1:{port}/healthz"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
        except httpx.RequestError:
            # Connection refused / timeout / any transport-level error —
            # means the server isn't up yet. Keep polling.
            pass
        else:
            if response.status_code == 200:
                return True
        time.sleep(_HEALTHZ_POLL_INTERVAL_S)
    return False
