"""Domain-level operations that cross scope boundaries.

``delete_domain`` joins ``rename_domain`` and ``create_domain`` as the
third exception to "every vault write goes through ``VaultWriter``" —
deleting a domain operates on the scope boundary itself and cannot be
modelled as a ``PatchSet`` (the PatchSet would need to target a
domain the caller is about to make unreachable).

Deletion strategy: nothing is ever ``rm -rf``'d. The folder is
``shutil.move``'d to ``<vault>/.brain/trash/<slug>-<ts>/`` where it
can be recovered by hand. A single undo record is written so
``brain_undo_last`` reverses the move by walking the trashed tree back
into place.

Hard rail: the ``personal`` slug is refused unconditionally. Personal
notes live behind the scope firewall and the default UI path must not
expose a one-click destroy for them. Administrators who genuinely want
to delete a personal domain can do so by hand.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,24}$")
_RESERVED_SLUGS: frozenset[str] = frozenset({"personal"})


@dataclass(frozen=True)
class DeletedDomainResult:
    """Outcome of a successful ``delete_domain`` call."""

    slug: str
    trash_path: Path
    undo_id: str
    files_moved: int


def _new_undo_id() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")


def _write_delete_domain_undo(
    *,
    undo_dir: Path,
    undo_id: str,
    slug: str,
    trash_path: Path,
    original_path: Path,
) -> None:
    """Persist a ``delete_domain`` undo record.

    The undo record carries enough to reverse the move: slug, trash
    location (where the folder lives now), and the original location
    (where the folder should return to). ``UndoLog.revert`` reads the
    ``KIND\tdelete_domain`` header and dispatches to the matching
    revert handler.
    """
    undo_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "KIND\tdelete_domain",
        f"SLUG\t{slug}",
        f"TRASH\t{trash_path}",
        f"ORIGINAL\t{original_path}",
    ]
    (undo_dir / f"{undo_id}.txt").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def delete_domain(
    vault_root: Path,
    slug: str,
    *,
    typed_confirm: bool,
) -> DeletedDomainResult:
    """Move ``<vault>/<slug>/`` into ``<vault>/.brain/trash/<slug>-<ts>/``.

    ``typed_confirm`` MUST be True — this is the primary safety rail. The
    frontend gathers a typed-``"delete"`` string and only calls through
    with ``typed_confirm=True`` once the user has typed it correctly.

    Raises:
        PermissionError: on ``typed_confirm=False``, reserved slugs
            (``personal``), or invalid slugs.
        FileNotFoundError: if the domain folder does not exist.
    """
    if not typed_confirm:
        raise PermissionError(
            "delete_domain requires typed_confirm=True — this moves the domain "
            "folder to trash and is only reversible via brain_undo_last"
        )
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"slug {slug!r} must match ^[a-z][a-z0-9-]{{1,24}}$"
        )
    if slug in _RESERVED_SLUGS:
        raise PermissionError(
            f"refusing to delete reserved domain {slug!r} — personal notes "
            "stay behind the scope firewall and must be removed by hand"
        )

    vault_root = vault_root.resolve()
    domain_dir = vault_root / slug
    if not domain_dir.exists() or not domain_dir.is_dir():
        raise FileNotFoundError(
            f"domain {slug!r} does not exist at {domain_dir}"
        )

    trash_root = vault_root / ".brain" / "trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")
    trash_path = trash_root / f"{slug}-{ts}"

    # Count files BEFORE the move — rglob against the source is the honest
    # answer; walking the trash post-move would double-read disk.
    files_moved = sum(1 for p in domain_dir.rglob("*") if p.is_file())

    shutil.move(str(domain_dir), str(trash_path))

    undo_id = _new_undo_id()
    _write_delete_domain_undo(
        undo_dir=vault_root / ".brain" / "undo",
        undo_id=undo_id,
        slug=slug,
        trash_path=trash_path,
        original_path=domain_dir,
    )

    return DeletedDomainResult(
        slug=slug,
        trash_path=trash_path,
        undo_id=undo_id,
        files_moved=files_moved,
    )
