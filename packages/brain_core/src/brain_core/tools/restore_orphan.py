"""brain_restore_orphan — clear the orphan mark on a vault note.

Plan 22 T5 / D2 non-destructive orphan policy. Reads the note's
frontmatter via :class:`brain_core.vault.frontmatter.Frontmatter`,
verifies ``orphaned == True``, sets ``orphaned: false`` and clears
``orphaned_at``. The body is left byte-identical — only two frontmatter
fields change.

The mutation lands through :meth:`brain_core.vault.writer.VaultWriter.apply`
with a single :class:`brain_core.vault.types.Edit` and
``include_orphans=True`` so the writer's pre-validation scope_guard
doesn't reject the target as "orphaned, opt in required" — this tool
is one of the explicit opt-in callers per T4.

Refuses if the note is not currently orphaned. The non-orphan path is
a programmer error: callers should not flip an already-clean note
because doing so silently does nothing AND leaves the user wondering
whether the call succeeded. The error wording suggests the natural
next action.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import (
    Frontmatter,
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import Edit, PatchSet

NAME = "brain_restore_orphan"
DESCRIPTION = (
    "Clear the orphan mark on a vault note (orphaned=false, orphaned_at=None). "
    "Body is unchanged. Refuses if the note is not currently orphaned. "
    "Routes through VaultWriter with include_orphans=True; undo log records the edit."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "note_path": {
            "type": "string",
            "description": "Absolute path to the vault note to restore.",
        },
    },
    "required": ["note_path"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    note_path_str = str(arguments["note_path"])
    note_path = Path(note_path_str)

    # Path validation: must be absolute. The writer's scope_guard would
    # raise on a non-absolute path too, but a friendlier error here saves
    # the caller a layer.
    if not note_path.is_absolute():
        raise ValueError(
            f"note_path must be absolute, got {note_path_str!r}"
        )

    # Scope check (include_orphans=True per T4). Resolves the path and
    # validates it lives inside vault_root / allowed_domains. This MUST
    # run before the read so a path outside scope can't even leak its
    # existence via OS errors.
    scope_guard(
        note_path,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
        include_orphans=True,
    )

    if not note_path.exists():
        raise FileNotFoundError(f"note not found: {note_path_str}")

    existing_content = note_path.read_text(encoding="utf-8")
    existing_fm_dict, _body = parse_frontmatter(existing_content)
    existing_fm = Frontmatter.from_dict(existing_fm_dict)

    if not existing_fm.orphaned:
        raise ValueError(
            f"note {note_path_str} is not orphaned; nothing to restore"
        )

    existing_domain = existing_fm.domain
    if existing_domain is None:
        # Defensive: a note with no domain frontmatter cannot be routed
        # through VaultWriter (allowed_domains=(...) needs a real slug).
        raise ValueError(
            f"note {note_path_str} has no `domain` frontmatter; "
            "cannot determine target domain for restore"
        )

    # Build the new content: same body, flipped frontmatter fields.
    new_fm = dict(existing_fm_dict)
    new_fm["orphaned"] = False
    new_fm["orphaned_at"] = None
    _fm, body = parse_frontmatter(existing_content)
    new_content = serialize_with_frontmatter(new_fm, body=body)

    edit = Edit(path=note_path, old=existing_content, new=new_content)
    patch = PatchSet(
        new_files=[],
        edits=[edit],
        index_entries=[],
        log_entry=None,
        reason="restore_orphan",
    )
    receipt = ctx.writer.apply(
        patch,
        allowed_domains=(existing_domain,),
        include_orphans=True,
    )

    return ToolResult(
        text=f"restored {note_path_str}",
        data={
            "status": "restored",
            "note_path": note_path_str,
            "undo_id": receipt.undo_id,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
