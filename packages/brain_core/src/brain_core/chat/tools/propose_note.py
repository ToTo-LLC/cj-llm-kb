"""propose_note tool — stage a new-note patch.

Brainstorm/Draft modes only (enforced by the mode-filtered registry in Task 16,
not by this tool directly). Constructs a PatchSet and stores it in the pending
queue. NEVER writes to the vault. The user approves the patch separately via
`brain patches apply`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import NewFile, PatchSet


class ProposeNoteTool:
    name = "propose_note"
    description = (
        "Stage a new note for approval. Does NOT write to the vault — the user applies it later."
    )
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["path", "content", "reason"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.pending_store is None:
            raise RuntimeError("propose_note requires pending_store in ToolContext")
        raw_path = str(args["path"])
        p = Path(raw_path)
        if p.is_absolute():
            raise ValueError("path must be vault-relative, not absolute")
        scope_guard(
            ctx.vault_root / p,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        patchset = PatchSet(
            new_files=[NewFile(path=p, content=str(args["content"]))],
            reason=str(args["reason"]),
        )
        envelope = ctx.pending_store.put(
            patchset=patchset,
            source_thread=ctx.source_thread,
            mode=ChatMode(ctx.mode_name),
            tool="propose_note",
            target_path=p,
            reason=str(args["reason"]),
        )
        return ToolResult(
            text=f"Staged new note at {p.as_posix()} (patch {envelope.patch_id}).",
            data={"patch_id": envelope.patch_id, "target_path": p.as_posix()},
            proposed_patch=envelope,
        )
