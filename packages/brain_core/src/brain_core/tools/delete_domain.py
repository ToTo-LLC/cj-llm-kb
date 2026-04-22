"""brain_delete_domain — move a top-level vault domain into trash.

Wraps :func:`brain_core.vault.domain.delete_domain`. Two hard rails
enforced at the tool boundary:

1. ``typed_confirm=True`` is mandatory — the frontend collects a typed
   ``"delete"`` string from the user before forwarding the call.
2. The ``personal`` slug is refused unconditionally — the privacy rail
   from ``CLAUDE.md`` means a one-click destroy for personal notes must
   not exist on the default UI path.

The folder is ``shutil.move``'d to ``<vault>/.brain/trash/<slug>-<ts>/``
and a ``KIND\tdelete_domain`` undo record is written so
``brain_undo_last`` fully reverses the operation.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.domain import delete_domain

NAME = "brain_delete_domain"
DESCRIPTION = (
    "Move a vault domain to <vault>/.brain/trash/ (reversible via brain_undo_last). "
    "Requires typed_confirm=True. Refuses the reserved 'personal' slug unconditionally."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"},
        "typed_confirm": {
            "type": "boolean",
            "default": False,
            "description": (
                "Must be true. The frontend sets this after the user types "
                "the confirmation string."
            ),
        },
    },
    "required": ["slug"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    slug = str(arguments["slug"])
    typed_confirm = bool(arguments.get("typed_confirm", False))

    result = delete_domain(ctx.vault_root, slug, typed_confirm=typed_confirm)

    return ToolResult(
        text=(
            f"deleted domain {slug!r} → moved to {result.trash_path} "
            f"(files_moved={result.files_moved}, undo_id={result.undo_id})"
        ),
        data={
            "status": "deleted",
            "slug": result.slug,
            "trash_path": str(result.trash_path),
            "files_moved": result.files_moved,
            "undo_id": result.undo_id,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
