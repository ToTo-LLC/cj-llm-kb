"""edit_open_doc tool — stage an exact-string replacement against the session's open doc.

Draft mode only (mode filtering enforced by registry, not this tool). Takes an
{old, new, reason} triple. Reads the open doc from disk, verifies that `old`
appears exactly once, and stages an Edit patch via PendingPatchStore. Never
writes to the vault — the user applies the patch separately.
"""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import Edit, PatchSet


class EditOpenDocTool:
    name = "edit_open_doc"
    description = (
        "Stage an exact-string replacement against the session's open doc. "
        "Does NOT write to the vault."
    )
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "old": {"type": "string"},
            "new": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["old", "new", "reason"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.open_doc_path is None:
            raise RuntimeError("edit_open_doc requires open_doc_path in ToolContext")
        if ctx.pending_store is None:
            raise RuntimeError("edit_open_doc requires pending_store in ToolContext")
        full = scope_guard(
            ctx.vault_root / ctx.open_doc_path,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not full.exists():
            raise FileNotFoundError(f"open doc {ctx.open_doc_path} not found")
        body = full.read_text(encoding="utf-8")
        old = str(args["old"])
        occurrences = body.count(old)
        if occurrences == 0:
            raise ValueError(f"old text not found in {ctx.open_doc_path}")
        if occurrences > 1:
            raise ValueError(f"old text not unique in {ctx.open_doc_path} ({occurrences} matches)")
        patchset = PatchSet(
            edits=[Edit(path=ctx.open_doc_path, old=old, new=str(args["new"]))],
            reason=str(args["reason"]),
        )
        envelope = ctx.pending_store.put(
            patchset=patchset,
            source_thread=ctx.source_thread,
            mode=ChatMode(ctx.mode_name),
            tool="edit_open_doc",
            target_path=ctx.open_doc_path,
            reason=str(args["reason"]),
        )
        return ToolResult(
            text=f"Staged edit to {ctx.open_doc_path.as_posix()} (patch {envelope.patch_id}).",
            data={"patch_id": envelope.patch_id},
            proposed_patch=envelope,
        )
