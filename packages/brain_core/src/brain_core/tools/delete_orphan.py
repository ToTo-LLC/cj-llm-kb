"""brain_delete_orphan — move an orphaned vault note into trash.

Plan 22 T5 / D2 + CLAUDE.md "destructive action requires typed
confirmation". Mirrors :mod:`brain_core.tools.delete_domain`'s shape:
the note is moved (not unlinked) into ``<vault>/.brain/trash/<date>/``
and an undo record is written so :class:`brain_core.vault.undo.UndoLog`
can restore it later.

Hard rails enforced at the tool boundary:

1. ``typed_confirm=True`` is mandatory — the frontend collects a typed
   ``"delete"`` string from the user before forwarding the call.
2. The note must currently be ``orphaned: true`` — destroying a
   non-orphan note is a separate operation (and never a one-click
   default; D2 keeps orphan adjudication explicit).

Undo strategy: rather than introduce a new undo kind (which would
require modifying :mod:`brain_core.vault.undo`), we write a legacy
``PATH`` + ``PREV_LEN`` undo record carrying the note's pre-delete
content. ``UndoLog.revert`` then RECREATES the file at the original
path with the captured content. The trash copy stays on disk
independently as an immutable audit trail — even after undo, the
``.brain/trash/<date>/<slug>.md`` file remains, so users can spot a
double-delete pattern. The undo log path is the formal recovery; the
trash copy is the belt-and-braces.
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import Frontmatter, parse_frontmatter
from brain_core.vault.paths import scope_guard

NAME = "brain_delete_orphan"
DESCRIPTION = (
    "Move an orphaned note to <vault>/.brain/trash/<date>/<slug>.md. "
    "Requires typed_confirm=True and the note must already be orphaned. "
    "Reversible via brain_undo_last (recreates the file at the original path)."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "note_path": {
            "type": "string",
            "description": "Absolute path to the orphaned vault note to delete.",
        },
        "typed_confirm": {
            "type": "boolean",
            "default": False,
            "description": (
                "Must be true. The frontend sets this after the user types "
                "the confirmation string."
            ),
        },
    },
    "required": ["note_path"],
}


def _new_undo_id() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")


def _write_per_file_undo_record(
    *, undo_dir: Path, undo_id: str, original_path: Path, prev_content: str
) -> None:
    """Write a legacy PATH + PREV_LEN undo record.

    The format matches :meth:`brain_core.vault.writer.VaultWriter._write_undo_record`
    so :meth:`brain_core.vault.undo.UndoLog.revert` recreates the file
    at ``original_path`` with ``prev_content`` on undo. We don't share
    the writer's private helper because:

    1. ``VaultWriter`` doesn't support "move to trash" as a Patch op;
       its surface is new_files / edits / index_entries.
    2. Mirroring the format inline keeps T5 strictly additive — no
       changes to :mod:`brain_core.vault.writer` or
       :mod:`brain_core.vault.undo`.
    """
    undo_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"PATH\t{original_path}",
        "PREV_LEN\t" + str(len(prev_content)),
        prev_content,
        "END_PREV",
    ]
    (undo_dir / f"{undo_id}.txt").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    note_path_str = str(arguments["note_path"])
    note_path = Path(note_path_str)
    typed_confirm = bool(arguments.get("typed_confirm", False))

    # Hard rail 1: typed_confirm. Refuse BEFORE the orphan check so a
    # missing confirm never reveals the note's orphan status.
    if not typed_confirm:
        raise PermissionError(
            "delete_orphan requires typed_confirm=True — this moves the note "
            "to trash and is only reversible via brain_undo_last"
        )

    if not note_path.is_absolute():
        raise ValueError(
            f"note_path must be absolute, got {note_path_str!r}"
        )

    # Scope check (include_orphans=True per T4). Resolves the path and
    # validates it lives inside vault_root / allowed_domains. Orphan-
    # opt-in is required because we're explicitly operating on an orphan.
    resolved = scope_guard(
        note_path,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
        include_orphans=True,
    )

    if not resolved.exists():
        raise FileNotFoundError(f"note not found: {note_path_str}")

    prev_content = resolved.read_text(encoding="utf-8")
    fm_dict, _body = parse_frontmatter(prev_content)
    fm = Frontmatter.from_dict(fm_dict)

    # Hard rail 2: must already be orphaned. Deleting a non-orphan is
    # a separate, more dangerous operation that is intentionally not
    # exposed via this tool.
    if not fm.orphaned:
        raise ValueError(
            f"note {note_path_str} is not orphaned; "
            "delete_orphan only operates on notes marked orphaned: true"
        )

    # Build trash destination: <vault>/.brain/trash/<YYYY-MM-DD>/<slug>.md
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    trash_root = ctx.vault_root / ".brain" / "trash" / today
    trash_root.mkdir(parents=True, exist_ok=True)
    slug = resolved.stem
    trash_path = trash_root / f"{slug}.md"
    # If a collision exists (e.g. two orphans with the same slug deleted
    # in one day), suffix with a microsecond timestamp so the trash
    # filename is unique. Mirrors the delete_domain.py timestamp pattern.
    if trash_path.exists():
        ts = datetime.now(tz=UTC).strftime("%H%M%S%f")
        trash_path = trash_root / f"{slug}-{ts}.md"

    # Move BEFORE writing the undo record so the trash file is the
    # canonical destination. If the move fails the undo record is never
    # written — the caller sees the OS error and the note stays in
    # place. If the move SUCCEEDS but the undo record write fails, we
    # raise but the file is already in trash; the user can copy it back
    # manually. Document this explicitly in the docstring above.
    shutil.move(str(resolved), str(trash_path))

    undo_id = _new_undo_id()
    _write_per_file_undo_record(
        undo_dir=ctx.vault_root / ".brain" / "undo",
        undo_id=undo_id,
        original_path=resolved,
        prev_content=prev_content,
    )

    return ToolResult(
        text=f"deleted {note_path_str} → {trash_path}",
        data={
            "status": "deleted",
            "trash_path": str(trash_path),
            "undo_id": undo_id,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
