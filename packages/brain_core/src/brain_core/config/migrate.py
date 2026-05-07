"""Plan 16 Task 41 — `brain config migrate` CLI core (D31).

Public entry point :func:`migrate_config_file` runs every active migration
helper against an on-disk ``config.json`` and rewrites the file in place
when something actually changed. Today there is exactly one helper
(:func:`brain_core.config.loader._migrate_legacy_autonomous` — Plan 16
T38); future schema rollovers chain on by adding to ``_MIGRATIONS``
and a corresponding label in :func:`_describe_migrations`.

Distinct from :func:`brain_core.config.loader.load_config`'s read-time
migration in three ways:

  1. **Backup file.** Original is copied to ``<path>.pre-migrate.bak``
     (or ``.bak.1`` / ``.bak.2`` / ... if a prior backup exists) BEFORE
     the rewrite. ``load_config`` never touches disk; the CLI does.
  2. **Explicit point-in-time rewrite.** ``load_config`` migrates the
     in-memory dict every read; the CLI persists the migrated form so
     the ``autonomous`` shape on disk matches the schema's current
     wire form (cleaner ``brain doctor`` output, simpler future
     migrations).
  3. **Hard-fail on missing / malformed input.** ``load_config`` falls
     back to defaults on parse error; the CLI raises so the user knows
     their explicit invocation didn't silently no-op.

The function deliberately operates on the raw dict pre-validation
(:class:`brain_core.config.schema.Config`'s ``model_validate`` is NOT
called). The whole point of running migrate is to fix old-shape data
that may not validate against the current schema until after migration
— validating mid-flight would defeat the purpose.

Atomic write contract mirrors :func:`brain_core.config.writer.save_config`
shape (``tempfile.NamedTemporaryFile`` in the parent dir → ``os.replace``)
but stays decoupled because (a) we don't have a ``Config`` object and
(b) we don't run inside the writer's filelock — migrate is a one-shot
human-driven CLI, not a runtime hot path. The temp file is cleaned up
on every failure mode (including ``KeyboardInterrupt``) so a partial
rewrite never lives at the canonical path.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brain_core.config.loader import _migrate_legacy_autonomous

# Bound on backup-suffix iteration. ``.pre-migrate.bak`` → ``.bak.1`` →
# ``.bak.2`` → ...; we stop at ``.bak.<MAX_BACKUP_SUFFIX>`` and raise.
# Rationale: a runaway loop would otherwise hang on a directory with
# millions of stale backup files (corrupted state). 100 is the right
# order of magnitude — a real user has at most a handful of migrate
# invocations across a vault's lifetime; anything past that is a bug.
_MAX_BACKUP_SUFFIX: int = 100


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of a :func:`migrate_config_file` call.

    Attributes:
        path: The file the migration ran against (resolved absolute).
        backup_path: The ``.pre-migrate.bak`` file written before the
            rewrite, or ``None`` if the run was a no-op.
        migrated: ``True`` if the file was rewritten; ``False`` on no-op.
        changes: Human-readable summary of what migrated. Empty list
            on no-op. Today the only entry is
            ``"autonomous: flat → nested"`` when the legacy autonomous
            shape was rewritten.
    """

    path: Path
    backup_path: Path | None
    migrated: bool
    changes: list[str] = field(default_factory=list)


# Each migration helper takes the raw dict and returns a possibly-mutated
# raw dict. Helpers MUST be idempotent — running a helper on its own
# output is a no-op (same dict shape, deep-equal). The label is the
# human-readable string :class:`MigrationResult.changes` will surface
# when the helper changed the dict.
#
# Contract: a helper "did something" if its output is NOT deep-equal
# to its input. We snapshot the pre-call dict (deep copy) and compare
# after — relying on identity / mutation flags would break helpers
# that legitimately return the same object on no-op (the existing T38
# helper does exactly this).
_MIGRATIONS: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = [
    ("autonomous: flat → nested", _migrate_legacy_autonomous),
]


def migrate_config_file(path: Path) -> MigrationResult:
    """Migrate the ``config.json`` at ``path`` from legacy shapes to the current schema.

    Algorithm:

      1. Read + parse the file. Missing file / malformed JSON / non-dict
         top level all raise (the user explicitly invoked migrate; failing
         loud is the right move — see module docstring).
      2. Run every helper in :data:`_MIGRATIONS` in order. Each helper
         is idempotent.
      3. If the post-migration dict is deep-equal to the parsed input,
         return a no-op :class:`MigrationResult` (no backup, no rewrite).
      4. Otherwise: copy the original to ``<path>.pre-migrate.bak`` (or
         the next free ``.bak.N`` slot — see :func:`_next_backup_path`),
         then atomically rewrite ``path`` with the migrated dict.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        json.JSONDecodeError: ``path`` is not valid JSON.
        ValueError: ``path`` parses but the top-level value is not a
            JSON object (a list / scalar / null).
        OSError: An I/O error during the backup copy or temp-file
            rewrite. The original ``path`` is untouched in this case
            (the rewrite stages to a temp file first, and we cleanup on
            failure).

    Returns:
        :class:`MigrationResult` describing what happened.
    """
    raw_text = path.read_text(encoding="utf-8")
    parsed = json.loads(raw_text)

    if not isinstance(parsed, dict):
        # Distinguished from json.JSONDecodeError — the JSON is well-
        # formed but the wrong shape. Same surface ``load_config`` uses
        # for the equivalent fallback, but here we raise instead of
        # warning + falling back: explicit user invocation, fail loud.
        raise ValueError(
            f"top-level JSON value in {path} is "
            f"{type(parsed).__name__}, expected object",
        )

    # Snapshot for the deep-equal comparison post-migration. Helpers may
    # mutate the dict in place (the existing T38 helper does on shape (2)
    # / (3)) so we need an independent copy of the pre-migration state.
    # ``json.loads(raw_text)`` is the cleanest deep copy available — it
    # guarantees the snapshot doesn't share aliased nested dicts/lists
    # with the live ``parsed`` object that helpers will mutate.
    pre_migration = json.loads(raw_text)

    # Run each helper. We collect changes by comparing the snapshot
    # against each helper's output — a helper "did something" if its
    # output is NOT deep-equal to the input we handed it. This handles
    # both the "in-place mutation" and "return new dict" idioms.
    changes: list[str] = []
    current = parsed
    for label, helper in _MIGRATIONS:
        before = json.loads(json.dumps(current))  # deep snapshot
        current = helper(current)
        if current != before:
            changes.append(label)

    if current == pre_migration:
        # No helper changed anything. Re-runs of an already-migrated file
        # land here. The user sees "No migration needed" + exit 0.
        return MigrationResult(
            path=path,
            backup_path=None,
            migrated=False,
            changes=[],
        )

    # We have a real migration. Stage to a temp file first, then rename.
    # The backup MUST land BEFORE the rewrite — if we crash between
    # backup and rewrite, the user has both the original (unchanged) and
    # the backup (an exact copy); they're not worse off than before
    # invoking migrate. If we crash between rewrite and... nothing, the
    # rewrite is atomic so the file is either old or new, never partial.
    backup = _next_backup_path(path)
    backup.write_bytes(path.read_bytes())

    payload = json.dumps(current, indent=2, sort_keys=True) + "\n"

    # ``tempfile.NamedTemporaryFile`` in the parent dir guarantees
    # ``os.replace`` is on the same filesystem (cross-device renames
    # raise ``OSError: [Errno 18]``). ``delete=False`` because we
    # explicitly manage cleanup — the file MUST live until ``os.replace``
    # consumes it, but MUST NOT live past any error before that.
    parent = path.parent
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=path.name,
        suffix=".tmp",
        dir=str(parent),
    )
    tmp_path = Path(tmp_name)
    try:
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(payload)
            os.replace(str(tmp_path), str(path))
        except BaseException:
            # BaseException so KeyboardInterrupt / SystemExit also scrub
            # the temp file. We re-raise immediately so signal semantics
            # are preserved. The backup file is left in place — the user
            # invoked migrate, the original is untouched at ``path``,
            # and the backup is an exact copy of that original. Removing
            # the backup on partial failure would surprise users who
            # noticed it appear in their file manager. Acceptable.
            tmp_path.unlink(missing_ok=True)
            # Rewind the backup too — symmetry with the temp-file scrub.
            # If the rewrite never landed, the backup is redundant
            # (the original is unchanged), and leaving stale backups
            # around on every failed run pollutes the user's vault.
            backup.unlink(missing_ok=True)
            raise
    finally:
        # Defensive cleanup: if ``os.replace`` succeeded, ``tmp_path``
        # is gone (replace consumes the source). If it failed, the
        # except branch above already unlinked. This second unlink is
        # a belt-and-suspenders "the file is definitely not here" guard
        # in case a future code path between fdopen+write and os.replace
        # introduces a third state. ``missing_ok=True`` keeps it cheap.
        tmp_path.unlink(missing_ok=True)

    return MigrationResult(
        path=path,
        backup_path=backup,
        migrated=True,
        changes=changes,
    )


def _next_backup_path(target: Path) -> Path:
    """Return the next free ``.pre-migrate.bak`` slot for ``target``.

    Iteration order:

      * ``<target>.pre-migrate.bak``         (no suffix)
      * ``<target>.pre-migrate.bak.1``
      * ``<target>.pre-migrate.bak.2``
      * ...
      * ``<target>.pre-migrate.bak.<MAX>`` (then raise)

    Stable: pre-existing backups are never overwritten. Plan 16 D31 pin
    test (c) covers this — pre-create ``.bak``, ``.bak.1``, ``.bak.2``
    and verify the next migration writes ``.bak.3``.

    Raises:
        RuntimeError: All ``_MAX_BACKUP_SUFFIX`` slots are taken.
            Surfaces a runaway loop / stale-backup pollution rather
            than spinning forever or silently overwriting.
    """
    base = target.with_name(target.name + ".pre-migrate.bak")
    if not base.exists():
        return base
    for n in range(1, _MAX_BACKUP_SUFFIX + 1):
        candidate = target.with_name(f"{target.name}.pre-migrate.bak.{n}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(
        f"refusing to create more than {_MAX_BACKUP_SUFFIX} pre-migrate "
        f"backups for {target}; clean up old .pre-migrate.bak* files first",
    )
