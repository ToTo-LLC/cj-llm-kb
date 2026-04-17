"""brain_undo_last — revert the most recent vault write via UndoLog.

Wraps :meth:`brain_core.vault.undo.UndoLog.revert`. The caller may pass an
explicit ``undo_id`` (as returned by any prior write tool in ``receipt.undo_id``
/ ``data['undo_id']``) or omit it, in which case we scan
``<vault>/.brain/undo/`` for the lex-last ``*.txt`` stem and revert that.
``UndoLog`` assigns undo_ids from ``datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')``
so lex order equals chronological order.

Intentionally unrate-limited. Undo is a safety/exit-ramp operation; gating it
behind the same ``patches`` bucket that guards forward writes would be
counterproductive — a user hitting the rate limit is exactly the user most
likely to want to undo.

If no undo records exist (missing or empty ``.brain/undo/``), returns a
``nothing_to_undo`` status rather than raising. If the caller supplies an
unknown ``undo_id``, ``UndoLog.revert`` raises ``FileNotFoundError`` and we
let it propagate — same pattern as ``brain_apply_patch`` / ``brain_reject_patch``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_undo_last"
DESCRIPTION = (
    "Revert the most recent vault write (or a specified undo_id) via UndoLog. "
    "Returns nothing_to_undo if no history exists."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "undo_id": {
            "type": "string",
            "description": (
                "Explicit undo_id to revert (as returned in `undo_id` by a "
                "prior write). Omit to revert the most recent."
            ),
        },
    },
}


def _find_latest_undo_id(vault_root: Path) -> str | None:
    """Return the lex-last undo_id under ``<vault>/.brain/undo/``, or None if empty."""
    undo_dir = vault_root / ".brain" / "undo"
    if not undo_dir.exists():
        return None
    files = sorted(undo_dir.glob("*.txt"))
    if not files:
        return None
    return files[-1].stem


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    undo_id = arguments.get("undo_id")
    if not undo_id:
        undo_id = _find_latest_undo_id(ctx.vault_root)
        if undo_id is None:
            return text_result(
                "nothing to undo — no undo history",
                data={"status": "nothing_to_undo"},
            )

    ctx.undo_log.revert(str(undo_id))  # FileNotFoundError on unknown id
    return text_result(
        f"reverted undo_id={undo_id}",
        data={"status": "reverted", "undo_id": undo_id},
    )
