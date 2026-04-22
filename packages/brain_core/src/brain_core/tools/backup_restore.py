"""brain_backup_restore — restore a snapshot over the current vault.

Wraps :func:`brain_core.backup.restore_from_snapshot`. Requires
``typed_confirm=True`` as a safety rail: restoring moves the current
vault contents into a timestamped ``<vault>-pre-restore-<ts>/`` trash
directory before extracting the snapshot, and the frontend is expected
to collect a typed ``"restore"`` confirmation before forwarding the
call.

Nothing is ever ``rm -rf``'d — restore is fully reversible by
inspecting the returned ``trash_path``.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.backup import restore_from_snapshot
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_backup_restore"
DESCRIPTION = (
    "Restore a vault snapshot over the current vault. Requires "
    "typed_confirm=True — the current vault contents are moved to a "
    "timestamped trash directory rather than deleted."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "backup_id": {"type": "string"},
        "typed_confirm": {
            "type": "boolean",
            "default": False,
            "description": (
                "Must be true. The frontend sets this after the user types "
                "the confirmation string."
            ),
        },
    },
    "required": ["backup_id"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    backup_id = str(arguments["backup_id"])
    typed_confirm = bool(arguments.get("typed_confirm", False))

    trash_path = restore_from_snapshot(
        ctx.vault_root,
        backup_id,
        typed_confirm=typed_confirm,
    )
    return ToolResult(
        text=(
            f"restored backup {backup_id!r} over vault (previous contents "
            f"moved to {trash_path})"
        ),
        data={
            "status": "restored",
            "backup_id": backup_id,
            "trash_path": str(trash_path),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
