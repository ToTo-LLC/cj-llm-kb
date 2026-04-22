"""brain_get_pending_patch — read a single staged patch by id (envelope + body).

Companion to :mod:`brain_core.tools.list_pending_patches`, which deliberately
omits the patchset body so the list endpoint never leaks staged content. Plan
07 Task 16's pending-screen detail pane needs the body to render
``new_files`` / ``edits`` / ``log_entry`` / ``index_entries`` for the
approver, so we expose a by-id read that returns the full envelope PLUS the
patchset.

Like the list tool, this is read-only against scratch state
(``<vault>/.brain/pending/<patch_id>.json``) — it never touches vault content
and therefore has no :func:`~brain_core.vault.paths.scope_guard` call. The
``patch_id`` itself is a simple slug (``{epoch_ms}-{uuid8}``) produced by
:class:`~brain_core.chat.pending.PendingPatchStore`; bypassing the store and
reading a raw path is not a supported code path.

Unknown ``patch_id`` raises ``KeyError`` (mirrors
:mod:`brain_core.tools.reject_patch` and :mod:`brain_core.tools.apply_patch`)
so transport wrappers surface a consistent 404-ish error shape.

No rate-limit check: reading is cheap, metadata-only, and does not stage
work.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_get_pending_patch"
DESCRIPTION = (
    "Fetch a single staged patch (envelope + patchset body) by patch_id. "
    "Used by the pending-approval detail pane. Raises KeyError on unknown id."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patch_id": {
            "type": "string",
            "description": "The patch_id returned by a prior staging tool (e.g. brain_propose_note).",
        },
    },
    "required": ["patch_id"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    patch_id = str(arguments["patch_id"])
    envelope = ctx.pending_store.get(patch_id)
    if envelope is None:
        raise KeyError(f"patch {patch_id!r} not found")

    # Split the envelope into (metadata, patchset) so the caller can treat
    # them independently. ``model_dump(mode="json")`` coerces ``Path`` and
    # ``datetime`` to JSON-safe primitives so the result round-trips through
    # FastAPI / MCP without custom encoders.
    full = envelope.model_dump(mode="json")
    patchset = full.pop("patchset")
    return ToolResult(
        text=f"patch {patch_id}: {envelope.tool} → {envelope.target_path}",
        data={
            "envelope": full,
            "patchset": patchset,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
