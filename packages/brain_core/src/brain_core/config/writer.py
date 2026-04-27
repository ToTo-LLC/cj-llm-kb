"""Atomic, locked, backup-on-write persistence for ``config.json`` (Plan 11 Task 2).

This module is the single seam every caller (D1 setup wizard, D2 settings UI,
D3 ``brain_config_set``, D6 backup-on-write) goes through to mutate the
on-disk config. The contract:

* ``<vault_root>/.brain/config.json`` is written atomically via temp+rename.
* Inter-process safety is enforced by ``filelock.FileLock`` on a sibling
  ``config.json.lock`` file. A timeout raises :class:`ConfigPersistenceError`
  with a user-facing message — never a bare ``filelock.Timeout``.
* On every successful write, the prior ``config.json`` (if any) is copied
  to ``config.json.bak`` before the new payload lands. This is D6's
  one-step rollback affordance.
* Only the Plan 11 D4 whitelist (``Config.persisted_dict()``) is serialized.
  ``vault_path`` and any other non-persisted field are filtered upstream.
* On POSIX we ``fsync`` the parent directory after rename so the rename is
  durable across power loss; Windows skips this (NTFS gives equivalent
  durability via ``MoveFileEx`` semantics that Python's ``os.replace`` uses).

This file lives at the ``config/`` layer, peer to ``loader.py``. It must
NOT import from ``brain_core.tools`` or ``brain_core.vault`` — the writer
is a primitive that those higher layers compose, not the other way around.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import filelock

from brain_core.config.schema import Config


class ConfigPersistenceError(Exception):
    """Raised when ``save_config`` cannot acquire the lock or write the file.

    Wraps ``filelock.Timeout`` (and any future I/O failure modes) into a
    single exception type so callers can render one user-facing error
    message instead of branching on the underlying SDK's exception tree.
    """


def _is_posix() -> bool:
    """Return ``True`` on POSIX platforms (Mac, Linux), ``False`` on Windows.

    Wrapped as a module-level function so tests can monkeypatch the
    branch without flipping ``os.name`` globally — patching ``os.name``
    re-flavors ``pathlib`` and breaks every ``Path`` operation that runs
    after the patch.
    """
    return os.name == "posix"


def _json_default(obj: object) -> str:
    """JSON encoder for types ``json.dumps`` does not handle natively.

    ``datetime`` is serialized via ``isoformat()`` so we get a real
    ISO-8601 string (``2026-05-01T12:00:00``) rather than ``str(dt)``'s
    space-separated form. ``Path`` becomes its string representation.
    Anything else raises ``TypeError`` — silent ``str()`` fallbacks would
    let an unexpected type ride into ``config.json`` undetected.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def save_config(
    config: Config,
    vault_root: Path,
    *,
    lock_timeout: float = 5.0,
) -> Path:
    """Persist ``config`` to ``<vault_root>/.brain/config.json`` atomically.

    The write is:

    1. Inter-process locked via ``filelock.FileLock`` on
       ``<vault_root>/.brain/config.json.lock``. Lock acquisition timeout
       raises :class:`ConfigPersistenceError`.
    2. Backed up: any existing ``config.json`` is copied to
       ``config.json.bak`` (preserving mtime) before the new payload is
       staged (Plan 11 D6).
    3. Staged to ``config.json.tmp`` with explicit LF newlines and UTF-8.
    4. Renamed atomically via ``os.replace`` (atomic on Mac+Windows).
    5. ``fsync``'d at the parent-directory level on POSIX so the rename
       survives power loss. Windows skips this step (no portable
       equivalent that's also atomic; ``os.replace`` already provides
       NTFS-level durability).

    The ``lock_timeout`` kwarg is primarily for tests — production callers
    should leave it at the default ``5.0``.

    Returns the absolute path of the written ``config.json``.
    """
    brain_dir = vault_root / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)

    target = brain_dir / "config.json"
    tmp = brain_dir / "config.json.tmp"
    backup = brain_dir / "config.json.bak"
    lock_path = brain_dir / "config.json.lock"

    payload = json.dumps(
        config.persisted_dict(),
        indent=2,
        sort_keys=True,
        default=_json_default,
    )

    lock = filelock.FileLock(str(lock_path))
    try:
        lock.acquire(timeout=lock_timeout)
    except filelock.Timeout as exc:
        raise ConfigPersistenceError(
            "another brain process is writing config.json; try again"
        ) from exc

    try:
        # D6: copy the existing config to .bak before we touch anything.
        # ``copy2`` preserves mtime so the backup reflects when the prior
        # config was last written, not when this save started.
        if target.exists():
            shutil.copy2(target, backup)

        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(payload)
            os.replace(tmp, target)
        except BaseException:
            # Mid-write failure: scrub the half-written tmp so a
            # subsequent save isn't confused by stale state. ``target``
            # is either untouched (replace never ran) or fully replaced
            # (replace is atomic) — either way no partial file lives at
            # the canonical path.
            tmp.unlink(missing_ok=True)
            raise

        # Durability: only POSIX gets a parent-dir fsync. On Windows
        # there's no portable, atomic equivalent — ``os.replace`` is
        # the durability ceiling we can offer there. The check is
        # routed through ``_is_posix()`` so tests can flip the branch
        # without monkeypatching ``os.name`` (which would re-flavor
        # ``pathlib`` mid-test and break every ``Path`` op).
        if _is_posix():
            dir_fd = os.open(str(brain_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        lock.release()

    return target
