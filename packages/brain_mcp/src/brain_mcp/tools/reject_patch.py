"""brain_reject_patch — reject a staged patch.

Wraps :meth:`brain_core.chat.pending.PendingPatchStore.reject`, which moves
the envelope from ``.brain/pending/<id>.json`` to
``.brain/pending/rejected/<id>.json`` with an updated reason. This is a
scratch-state transition only — the vault itself is never touched, so there
is no :class:`VaultWriter` involvement and no undo record.

Unknown patch_id raises ``KeyError`` from the store; we let it propagate so
the MCP session error wraps it uniformly (same pattern as
``brain_apply_patch``).

No rate-limit check: rejecting is cheap, metadata-only, and idempotent from
the caller's perspective — it should always succeed if the patch exists.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_reject_patch"
DESCRIPTION = (
    "Reject a staged patch. Moves the envelope to pending/rejected/ with the given reason."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patch_id": {
            "type": "string",
            "description": "The patch_id returned by a prior staging tool (e.g. brain_propose_note).",
        },
        "reason": {
            "type": "string",
            "description": "Human-readable rejection reason; replaces the envelope's reason on disk.",
        },
    },
    "required": ["patch_id", "reason"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    patch_id = str(arguments["patch_id"])
    reason = str(arguments["reason"])
    ctx.pending_store.reject(patch_id, reason=reason)  # raises KeyError on unknown
    return text_result(
        f"rejected patch {patch_id}",
        data={"status": "rejected", "patch_id": patch_id, "reason": reason},
    )
