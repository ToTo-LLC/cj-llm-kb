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
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import filelock

from brain_core.config.schema import Config


class ConfigPersistenceError(Exception):
    """Raised when ``save_config`` cannot acquire the lock or write the file.

    Wraps ``filelock.Timeout`` (and any future I/O failure modes) into a
    single exception type so callers can render one user-facing error
    message instead of branching on the underlying SDK's exception tree.

    Carries optional structured fields so callers (the Plan 11 Task 4
    mutation tools) can render uniform error UX without parsing the
    message string. ``attempted_path`` is the resolved target path the
    writer was about to commit to; ``cause`` is a short stable token
    (e.g. ``"lock_timeout"``, ``"replace_failed"``) the UI layer can
    branch on. Both default to ``None`` so direct
    ``raise ConfigPersistenceError("msg")`` callers stay valid.
    """

    def __init__(
        self,
        message: str,
        *,
        attempted_path: Path | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(message)
        self.attempted_path = attempted_path
        self.cause = cause


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

    Intentionally narrow — only handles types currently surfaced by
    ``Config.persisted_dict()``. Add a branch when a real persisted
    field requires a new type (e.g. ``Decimal``, ``UUID``) rather than
    expanding speculatively. The unknown-type ``TypeError`` is the
    safety net that forces this decision to be deliberate.
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
            "another brain process is writing config.json; try again",
            attempted_path=target,
            cause="lock_timeout",
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
            # BaseException (not Exception) so KeyboardInterrupt /
            # SystemExit mid-write also scrubs tmp; we re-raise
            # immediately so signal semantics are preserved. ``target``
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


@contextmanager
def persist_config_or_revert(config: Config, vault_root: Path) -> Iterator[None]:
    """Snapshot, yield for in-place mutation, persist, revert on failure.

    Plan 11 Task 4 helper for the five mutation tools (``brain_config_set``,
    ``brain_create_domain``, ``brain_rename_domain``, ``brain_delete_domain``,
    ``brain_budget_override``). Each tool's pre-Task-4 shape was "mutate
    ``ctx.config`` in-place, return". Each becomes::

        with persist_config_or_revert(ctx.config, ctx.vault_root):
            ctx.config.domains.append(slug)

    The yield happens AFTER the deep snapshot but BEFORE :func:`save_config`,
    so the caller's mutations land on the live ``Config`` first; the writer
    serializes the post-mutation state. If anything between the snapshot
    and a successful ``save_config`` raises (caller's mutation, schema
    validation, lock timeout, disk write), the snapshot's field values
    are copied back over ``config`` via ``setattr`` and the exception
    re-raises.

    Why ``setattr`` per field instead of swapping the reference: every
    caller is a tool whose ``ToolContext`` is ``@dataclass(frozen=True)``,
    so reassigning ``ctx.config`` raises ``FrozenInstanceError``. Mutating
    the existing object in place keeps the caller's reference live.

    Why catch bare ``Exception``: the helper only needs to revert when
    something — caller mutation OR ``save_config`` — actually changed
    state. If the caller's mutation raises before ``save_config`` runs,
    the snapshot revert is still the right move (it restores the
    pre-mutation state) and is idempotent on partial mutations. The
    caller-visible exception is preserved via re-raise.

    KeyboardInterrupt / SystemExit are *not* caught — those should
    propagate without revert so the user sees the original signal and
    we don't paper over an interactive abort.
    """
    snapshot = config.model_copy(deep=True)
    try:
        yield
        save_config(config, vault_root)
    except Exception:
        for field_name in type(config).model_fields:
            setattr(config, field_name, getattr(snapshot, field_name))
        raise
