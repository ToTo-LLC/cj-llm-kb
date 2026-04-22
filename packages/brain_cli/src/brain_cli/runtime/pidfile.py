"""Cross-platform PID file helpers for the brain supervisor.

The supervisor treats a PID file as authoritative metadata about the
currently-running daemon, but NEVER trusts it alone: every read is
paired with a psutil liveness check *and* a cmdline sanity check so a
recycled PID (say, a completely unrelated Safari process that happens to
have inherited the old brain PID after a reboot) doesn't trick us into
thinking the daemon is live.

Three states the supervisor cares about:

* pid file missing            → no daemon running
* pid file → alive + brain_api → daemon running, "already running" path
* pid file → dead or wrong name → stale, delete + continue with fresh spawn
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import psutil

# A cmdline token that uniquely identifies "this process is our brain_api".
# The supervisor spawns uvicorn with our factory module on argv, so we can
# grep cmdlines for this string. Keeping it a single constant means a
# future factory rename is a one-line change.
_BRAIN_API_CMDLINE_TOKEN = "brain_cli.runtime.backend_factory"


def write_pid(path: Path, pid: int) -> None:
    """Write the PID to ``path``, creating parent directories if needed.

    Uses pathlib for cross-platform path handling and writes in text mode
    with a trailing newline (convention; some tools tail PID files).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{pid}\n", encoding="utf-8")


def read_pid(path: Path) -> int | None:
    """Return the PID from ``path``, or None if missing or unparseable.

    Unparseable contents are treated as "missing" rather than raising —
    a garbled pid file is equivalent to a stale one, and the caller's
    next step is to delete + respawn either way.
    """
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def is_alive(pid: int) -> bool:
    """Return True iff ``pid`` refers to a running process.

    Wraps ``psutil.pid_exists``. The Plan 08 spec requires this to work
    identically on Mac + Windows — psutil's wrapper takes care of the
    platform differences (POSIX ``kill(pid, 0)`` vs Windows
    ``OpenProcess``).
    """
    try:
        return psutil.pid_exists(pid)
    except Exception:
        # psutil can raise on exotic platforms; treat "I can't tell" as
        # "probably not alive" so we err toward a fresh spawn.
        return False


def is_brain_api(pid: int) -> bool:
    """Return True iff the live process at ``pid`` is our brain_api daemon.

    Checks the process's cmdline for our factory module token. Returns
    False on any psutil error (NoSuchProcess, AccessDenied, ZombieProcess)
    — the supervisor treats those as "stale" and will delete the pid file.

    Windows cmdline can be empty on some system processes; our own
    uvicorn invocation always has the factory module on argv, so an
    empty cmdline also returns False (stale).
    """
    try:
        proc = psutil.Process(pid)
        cmdline = proc.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception:
        # Any other psutil-internal failure: err toward False.
        return False

    # Match our factory module anywhere on the cmdline. This is a string
    # check rather than an exact argv position because uvicorn's argv
    # shape differs slightly between `uv run uvicorn ...` (wrapper) and
    # direct `python -m uvicorn ...` invocations.
    return any(_BRAIN_API_CMDLINE_TOKEN in str(arg) for arg in cmdline)


def delete_pid(path: Path) -> None:
    """Remove the PID file. Idempotent — missing file is fine."""
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
