"""brain_list_pending_patches — list staged patches without exposing bodies.

Wraps :meth:`brain_core.chat.pending.PendingPatchStore.list` and projects each
``PendingEnvelope`` down to its metadata fields only. The patchset body
(``new_files``, ``edits``, ``log_entry``, ``index_entries``) is deliberately
omitted — a caller who needs the body uses a future ``brain_inspect_patch``
tool (out of scope for Plan 04). Emitting body content here would leak staged
content to any MCP client with list access.

No rate-limit check: listing is read-only, cheap, and does not stage work.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_list_pending_patches"
DESCRIPTION = (
    "List staged patches (pending human approval). Returns envelope metadata "
    "only — patchset bodies are NOT included."
)
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_LIMIT},
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    limit = min(int(arguments.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)
    envelopes = ctx.pending_store.list()[:limit]
    patches = [
        {
            "patch_id": env.patch_id,
            "created_at": env.created_at.isoformat(),
            "tool": env.tool,
            "target_path": str(env.target_path),
            "reason": env.reason[:200],  # truncate long reasons
            "mode": env.mode.value,
        }
        for env in envelopes
    ]
    lines = [f"- {p['patch_id']} {p['tool']} → {p['target_path']}" for p in patches] or [
        "(no pending patches)"
    ]
    return ToolResult(
        text="\n".join(lines),
        data={"count": len(patches), "patches": patches},
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
