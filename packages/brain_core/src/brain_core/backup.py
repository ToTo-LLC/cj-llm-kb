"""Vault backup snapshots — tarball-based point-in-time archives.

A snapshot is a gzip-compressed tarball of the vault root, excluding
ephemeral / sensitive paths (``.brain/run/``, ``.brain/logs/``, and
``.brain/secrets.env``). Snapshots live under ``<vault>/.brain/backups/``
and are named ``<YYYYMMDDTHHMMSSffffff>-<trigger>.tar.gz`` so lex order
equals chronological order.

Triggers:
  * ``manual`` — user clicked the "Back up now" button.
  * ``daily`` — scheduled cron-style backup.
  * ``pre_bulk_import`` — automatic safety net before a bulk import.

Restore strategy: the current vault contents (except the backups folder
itself and ``.brain/secrets.env``) are moved to a timestamped trash
directory ``<vault>-pre-restore-<ts>/`` BEFORE the tarball is extracted.
Nothing is ever ``rm -rf``'d — restore is reversible by hand if the user
decides after the fact. ``typed_confirm=True`` is mandatory: restores are
irreversible in the happy path and we refuse the call without an explicit
opt-in from the caller.

Cross-platform: ``pathlib``, ``tarfile``, ``shutil.move``, UTF-8 text
everywhere. No shell calls, no POSIX-only APIs. Tested on Mac + Windows.
"""

from __future__ import annotations

import re
import shutil
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

BackupTrigger = Literal["manual", "daily", "pre_bulk_import"]

_VALID_TRIGGERS: frozenset[str] = frozenset({"manual", "daily", "pre_bulk_import"})
_FILENAME_RE = re.compile(
    r"^(?P<ts>\d{8}T\d{6}\d{6})-(?P<trigger>manual|daily|pre_bulk_import)\.tar\.gz$"
)


@dataclass(frozen=True)
class BackupMeta:
    """Describes a single snapshot on disk."""

    backup_id: str  # filename stem before ``.tar.gz`` — globally unique
    path: Path  # absolute path to the tarball
    trigger: BackupTrigger
    created_at: datetime  # parsed from the filename timestamp
    size_bytes: int
    file_count: int


def _backups_dir(vault_root: Path) -> Path:
    return vault_root / ".brain" / "backups"


def _new_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")


def _parse_timestamp(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y%m%dT%H%M%S%f").replace(tzinfo=UTC)


def _should_exclude(vault_root: Path, candidate: Path) -> bool:
    """Return True if ``candidate`` lives in an ephemeral/sensitive path."""
    try:
        rel = candidate.resolve().relative_to(vault_root.resolve())
    except ValueError:
        return True  # outside the vault — never archive
    parts = rel.parts
    if not parts:
        return False
    # Always skip the backups folder itself (no recursive bombs).
    if parts[:2] == (".brain", "backups"):
        return True
    if parts[:2] == (".brain", "run"):
        return True
    if parts[:2] == (".brain", "logs"):
        return True
    return parts == (".brain", "secrets.env")


def create_snapshot(
    vault_root: Path,
    trigger: BackupTrigger = "manual",
) -> BackupMeta:
    """Create a tarball snapshot of ``vault_root``.

    The trigger is recorded in the filename. A fresh timestamped filename
    is minted on every call so two rapid-fire backups cannot collide.

    Raises:
        FileNotFoundError: if ``vault_root`` does not exist.
        ValueError: if ``trigger`` is not one of the supported triggers.
    """
    if trigger not in _VALID_TRIGGERS:
        raise ValueError(f"trigger {trigger!r} must be one of {sorted(_VALID_TRIGGERS)}")
    vault_root = vault_root.resolve()
    if not vault_root.exists():
        raise FileNotFoundError(f"vault_root {vault_root} does not exist")

    backups_dir = _backups_dir(vault_root)
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = _new_timestamp()
    backup_id = f"{ts}-{trigger}"
    tarball_path = backups_dir / f"{backup_id}.tar.gz"

    file_count = 0

    def _filter(
        tarinfo: tarfile.TarInfo,
    ) -> tarfile.TarInfo | None:
        # tarinfo.name is relative to the arcname base ("vault").
        nonlocal file_count
        # Strip the leading "vault/" arcname to get a vault-relative path.
        rel = tarinfo.name
        if rel.startswith("vault/"):
            rel = rel[len("vault/") :]
        elif rel == "vault":
            # The top-level directory entry itself — keep it.
            return tarinfo
        rel_path = vault_root / rel
        if _should_exclude(vault_root, rel_path):
            return None
        if tarinfo.isfile():
            file_count += 1
        return tarinfo

    # arcname="vault" so the tarball always extracts under a stable root
    # regardless of the source vault directory name.
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(str(vault_root), arcname="vault", filter=_filter)

    size_bytes = tarball_path.stat().st_size
    return BackupMeta(
        backup_id=backup_id,
        path=tarball_path,
        trigger=trigger,
        created_at=_parse_timestamp(ts),
        size_bytes=size_bytes,
        file_count=file_count,
    )


def list_snapshots(vault_root: Path) -> list[BackupMeta]:
    """Return every snapshot under ``<vault>/.brain/backups/``, newest first.

    Malformed filenames are silently skipped so a user's hand-dropped tarball
    in the backups dir does not break the listing.
    """
    backups_dir = _backups_dir(vault_root.resolve())
    if not backups_dir.exists():
        return []
    out: list[BackupMeta] = []
    for candidate in sorted(backups_dir.iterdir()):
        if not candidate.is_file():
            continue
        match = _FILENAME_RE.match(candidate.name)
        if not match:
            continue
        ts = match.group("ts")
        trigger_str = match.group("trigger")
        trigger: BackupTrigger = trigger_str  # type: ignore[assignment]
        size_bytes = candidate.stat().st_size
        # Counting member files means opening the tarball — O(files) per
        # archive, but list_snapshots is called from the UI sparingly.
        try:
            with tarfile.open(candidate, "r:gz") as tar:
                file_count = sum(1 for m in tar.getmembers() if m.isfile())
        except tarfile.TarError:
            file_count = 0
        out.append(
            BackupMeta(
                backup_id=candidate.stem.removesuffix(".tar"),
                path=candidate,
                trigger=trigger,
                created_at=_parse_timestamp(ts),
                size_bytes=size_bytes,
                file_count=file_count,
            )
        )
    # Newest first — lex-descending timestamp.
    out.sort(key=lambda m: m.created_at, reverse=True)
    return out


def restore_from_snapshot(
    vault_root: Path,
    backup_id: str,
    *,
    typed_confirm: bool = False,
) -> Path:
    """Restore ``backup_id`` over ``vault_root``. Returns the pre-restore trash dir.

    ``typed_confirm`` MUST be True. Restoring is destructive (the current
    vault state is replaced), so we refuse the call without an explicit
    opt-in — even though nothing is actually deleted (existing content is
    moved to ``<vault>-pre-restore-<ts>/``, never removed).

    Raises:
        PermissionError: if ``typed_confirm`` is not True.
        FileNotFoundError: if the backup does not exist.
        tarfile.TarError: if the tarball fails integrity verification.
    """
    if not typed_confirm:
        raise PermissionError(
            "restore requires typed_confirm=True — this replaces the current vault"
        )
    vault_root = vault_root.resolve()
    backups_dir = _backups_dir(vault_root)
    tarball_path = backups_dir / f"{backup_id}.tar.gz"
    if not tarball_path.exists():
        raise FileNotFoundError(f"backup {backup_id!r} not found at {tarball_path}")

    # Integrity check before we move anything.
    with tarfile.open(tarball_path, "r:gz") as tar:
        _ = tar.getmembers()  # lazily validates the archive

    # Move current vault contents to a pre-restore trash dir. The backups
    # folder stays in place (we don't want to lose the snapshot we're about
    # to extract from), and ``.brain/secrets.env`` stays put — restoring
    # should not clobber the user's API key.
    ts = _new_timestamp()
    trash_dir = vault_root.parent / f"{vault_root.name}-pre-restore-{ts}"
    trash_dir.mkdir(parents=True, exist_ok=False)

    for child in list(vault_root.iterdir()):
        if child.name == ".brain":
            # Preserve backups + secrets; move the rest of .brain to trash.
            brain_trash = trash_dir / ".brain"
            brain_trash.mkdir(parents=True, exist_ok=True)
            for inner in list(child.iterdir()):
                if inner.name == "backups":
                    continue
                if inner.name == "secrets.env":
                    continue
                shutil.move(str(inner), str(brain_trash / inner.name))
            continue
        shutil.move(str(child), str(trash_dir / child.name))

    # Extract the tarball. The archive is rooted at ``vault/``; unpack the
    # contents INTO vault_root (not alongside), hence the manual member
    # rewrite. ``filter='data'`` (Python 3.12+) blocks absolute paths and
    # traversal attempts.
    with tarfile.open(tarball_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.name.startswith("vault"):
                continue
            # Strip the "vault/" prefix.
            new_name = member.name[len("vault") :].lstrip("/")
            if not new_name:
                continue
            member.name = new_name
            tar.extract(member, path=vault_root, filter="data")

    return trash_dir
