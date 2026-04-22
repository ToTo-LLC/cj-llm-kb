"""Atomic staging + swap for ``brain upgrade``.

Plan 08 Task 5. Three operations, all cross-platform:

* :func:`stage_upgrade` extracts a downloaded tarball into
  ``<install_dir>-staging/``.
* :func:`swap_in` renames ``<install_dir>`` → ``<install_dir>-prev-<ts>/``,
  then renames the staging dir into place. Returns the backup path so
  the caller can keep / clean up old backups per policy.
* :func:`rollback_swap` reverses a swap after the fact — used when a
  post-swap step (restart, smoke test) fails and we need to drop back
  to the previous install.

**Cross-platform:** rename is atomic on POSIX and on Windows for files +
dirs on the *same filesystem*. The install dir and staging dir are
always siblings (``brain/`` + ``brain-staging/``), so this is always
the case for us. Documenting the invariant here because Linux tmpfs /
Windows reparse-point shenanigans CAN violate it — we just don't hit
that configuration in practice.

**Windows file-locking:** a running daemon holds handles on its own
executables (Python .pyd DLLs etc.), which blocks any rename of the
parent directory. The ``upgrade`` command MUST call ``brain stop``
before ``swap_in``. Even after stop, Windows sometimes lingers on
closed handles for a handful of milliseconds — we retry three times
with a 500 ms backoff before giving up.
"""

from __future__ import annotations

import contextlib
import shutil
import sys
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path


class SwapError(RuntimeError):
    """Any failure in stage / swap / rollback.

    One error type because the caller's response is always the same:
    surface the message + exit 1 with a manual-recovery hint.
    """


# Number of rename retries before giving up. Windows sometimes holds a
# handle on a just-stopped process's files for a few tens of milliseconds.
_RENAME_RETRIES = 3
_RENAME_BACKOFF_S = 0.5


def _retry_rename(src: Path, dst: Path) -> None:
    """Retry ``Path.rename`` on transient Windows file-lock errors.

    POSIX paths hit the happy path on the first attempt. On Windows,
    ``PermissionError`` and ``OSError`` (for in-use files) get three
    chances spaced 500 ms apart before we give up.
    """
    last_exc: BaseException | None = None
    for attempt in range(_RENAME_RETRIES):
        try:
            src.rename(dst)
            return
        except (PermissionError, OSError) as exc:
            last_exc = exc
            if sys.platform != "win32" or attempt == _RENAME_RETRIES - 1:
                # POSIX: no reason to retry, the FS said no.
                # Last Windows attempt: out of patience.
                raise
            time.sleep(_RENAME_BACKOFF_S)
    # Unreachable — either returned on success or re-raised.
    assert last_exc is not None
    raise last_exc


def _staging_dir_for(install_dir: Path) -> Path:
    """Sibling staging dir next to the install dir.

    Same parent = same filesystem = atomic rename. Exposed as a
    module-level helper so tests can assert on the layout.
    """
    return install_dir.parent / f"{install_dir.name}-staging"


def stage_upgrade(install_dir: Path, tarball: Path) -> Path:
    """Extract ``tarball`` into ``<install_dir>-staging/`` and return that path.

    Raises :class:`SwapError` if the staging dir already exists — the
    caller is responsible for cleaning up prior failed attempts (so we
    never silently overwrite someone else's work-in-progress).
    """
    if not tarball.exists():
        raise SwapError(f"Tarball not found: {tarball}")

    staging = _staging_dir_for(install_dir)
    if staging.exists():
        raise SwapError(
            f"Staging dir already exists: {staging}. "
            "Clean it up before upgrading (rm -rf or Remove-Item)."
        )

    staging.mkdir(parents=True, exist_ok=False)

    try:
        # ``r:gz`` auto-decompresses. ``tarfile`` is pure Python and
        # works identically on POSIX + Windows.
        with tarfile.open(str(tarball), mode="r:gz") as tf:
            _safe_extract(tf, staging)
    except Exception as exc:
        # Partial extract on disk — back out so callers can retry
        # without the "staging already exists" guard tripping.
        _force_rmtree(staging)
        raise SwapError(f"Failed to extract tarball: {exc}") from exc

    return staging


def _safe_extract(tf: tarfile.TarFile, target: Path) -> None:
    """Extract tarball members into ``target``, rejecting path traversal.

    Python 3.12's ``tarfile`` ships ``data_filter`` which does this by
    default, but we guard explicitly too — defense in depth against a
    malicious release tarball with ``../`` members. Any member whose
    resolved path escapes ``target`` raises SwapError.
    """
    target_resolved = target.resolve()
    for member in tf.getmembers():
        # Resolve the member's target path relative to ``target`` and
        # confirm it stays inside. Use os.path.join + resolve because
        # ``Path(target) / member.name`` normalizes ``..`` for us.
        member_path = (target / member.name).resolve()
        try:
            member_path.relative_to(target_resolved)
        except ValueError as exc:
            raise SwapError(f"Tarball member escapes extraction root: {member.name}") from exc
    # Python 3.12+: data_filter rejects setuid, device files, absolute
    # paths, and links outside the extraction target. Passing it
    # explicitly keeps us compatible with older 3.12 patch releases
    # where the default hasn't flipped yet.
    tf.extractall(str(target), filter="data")


def swap_in(staging_dir: Path, install_dir: Path) -> Path:
    """Atomically replace ``install_dir`` with ``staging_dir``.

    The old install is renamed to ``<install_dir>-prev-<UTC-timestamp>/``
    and that path is returned. Callers decide how many backups to keep;
    this function never deletes anything.

    If ``install_dir`` doesn't exist yet (first install via upgrade flow
    somehow), we skip the backup rename and just promote staging — the
    returned path is the nonexistent backup path for symmetry with the
    rollback signature.
    """
    if not staging_dir.exists():
        raise SwapError(f"Staging dir missing: {staging_dir}")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = install_dir.parent / f"{install_dir.name}-prev-{timestamp}"

    if install_dir.exists():
        try:
            _retry_rename(install_dir, backup)
        except OSError as exc:
            raise SwapError(
                f"Could not move current install to backup: {exc}. "
                f"Is brain running? Try `brain stop` first."
            ) from exc

    try:
        _retry_rename(staging_dir, install_dir)
    except OSError as exc:
        # Rollback the backup rename we just did so we don't leave the
        # user with no install dir at all.
        if backup.exists() and not install_dir.exists():
            # Genuinely broken if this also fails — surface both failures
            # by swallowing the secondary and letting the primary raise.
            with contextlib.suppress(OSError):
                _retry_rename(backup, install_dir)
        raise SwapError(f"Could not promote staging to install: {exc}.") from exc

    return backup


def rollback_swap(backup_dir: Path, install_dir: Path) -> None:
    """Reverse :func:`swap_in` — delete the broken install, restore the backup.

    Used when a post-swap step (uv sync in the new dir, DB migration,
    restart smoke test) fails and we want to drop back to the previous
    install. Safe to call even if ``install_dir`` doesn't exist yet
    (e.g. swap_in itself failed partway through).
    """
    if not backup_dir.exists():
        raise SwapError(f"Backup dir missing — cannot rollback: {backup_dir}")

    if install_dir.exists():
        _force_rmtree(install_dir)

    try:
        _retry_rename(backup_dir, install_dir)
    except OSError as exc:
        raise SwapError(
            f"Could not restore backup {backup_dir} → {install_dir}: {exc}. "
            f"Manual recovery: rename the backup dir by hand."
        ) from exc


def _force_rmtree(path: Path) -> None:
    """``shutil.rmtree`` with Windows read-only handling.

    Windows sometimes marks files (especially Python ``__pycache__``
    entries) read-only, which ``rmtree`` refuses by default. The
    ``onexc`` hook clears the flag and retries. Harmless no-op on POSIX.
    """

    def _on_error(func: object, target: str, exc: BaseException) -> None:
        # Make the target writable and retry. If this still fails, let
        # the exception propagate — we've done what we can.
        with contextlib.suppress(OSError):
            Path(target).chmod(0o700)
        # Invoke the original function (unlink/rmdir) again.
        if callable(func):
            with contextlib.suppress(OSError):
                func(target)  # type: ignore[call-arg]
                return

    # Python 3.12+ prefers ``onexc`` over the deprecated ``onerror``.
    shutil.rmtree(path, onexc=_on_error)  # type: ignore[call-arg]
