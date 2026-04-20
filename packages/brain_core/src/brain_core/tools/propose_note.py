"""brain_propose_note — stage a new-note patch.

Construct a :class:`PatchSet` with one :class:`NewFile` and stage it via
``ctx.pending_store``. This tool NEVER writes to the vault — the user applies
the envelope later through ``brain_apply_patch``. The approval-gated flow here
mirrors the web app exactly (spec principle #3: LLM writes are always staged).

Rate limiter consumes from the ``patches`` bucket (cost=1) BEFORE any other
work so a refused call is cheap and deterministic. ChatMode.BRAINSTORM is the
closest semantic match for "staged for human approval"; MCP has no chat mode,
so we reuse it (same placeholder used by ``brain_ingest``).
TODO(plan-05+): consider a dedicated ``ChatMode.MCP`` value so MCP-origin
pending patches are distinguishable from brainstorm-origin ones in the
patch queue UI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path
from brain_core.vault.types import NewFile, PatchSet

NAME = "brain_propose_note"
DESCRIPTION = (
    "Stage a new note for approval. Does NOT write to the vault — "
    "the user applies it via brain_apply_patch."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Vault-relative path like 'research/notes/foo.md'",
        },
        "content": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["path", "content", "reason"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    # Rate-limit check FIRST — a refused call must not reach scope_guard,
    # pending-store IO, or any other side effect.
    if not ctx.rate_limiter.check("patches", cost=1):
        return ToolResult(
            text="rate limited (patches/min)",
            data={"status": "rate_limited", "bucket": "patches", "retry_after_seconds": 60},
        )

    raw_path = str(arguments["path"])
    # scope_guard_path raises ValueError("...vault-relative...") on absolute
    # input and ScopeError on out-of-scope resolved paths. Both bubble up.
    scope_guard_path(raw_path, ctx)
    p = Path(raw_path)

    patchset = PatchSet(
        new_files=[NewFile(path=p, content=str(arguments["content"]))],
        reason=str(arguments["reason"]),
    )
    envelope = ctx.pending_store.put(
        patchset=patchset,
        source_thread="mcp-propose",
        # ChatMode.BRAINSTORM is the closest semantic match for "staged for
        # human approval". TODO(plan-05+): dedicated ``ChatMode.MCP`` value.
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=p,
        reason=str(arguments["reason"]),
    )
    return ToolResult(
        text=f"staged new note at {p.as_posix()} (patch {envelope.patch_id})",
        data={
            "status": "pending",
            "patch_id": envelope.patch_id,
            "target_path": p.as_posix(),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
