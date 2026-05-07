"""brain_repair_config_apply — write a repaired config payload to disk.

Plan 16 Task 33 / D28 step 1 of 3 — sibling of
:mod:`brain_core.tools.repair_config`. The diagnostic tool returns a
``repaired_config`` payload; this tool takes that payload back as input,
validates it through :class:`brain_core.config.schema.Config`, and persists
it via :func:`brain_core.config.writer.save_config`.

Adjudicated **Option 1** (two tools, two responsibilities) per the Task 33
dispatch text. The shape mirrors :mod:`brain_core.tools.backup_create` /
:mod:`brain_core.tools.backup_restore` — read-side tool diagnoses, write-side
tool commits. Keeping them split means the frontend's two-action flow
(Re-run / Re-apply) hits independent endpoints with independent error
surfaces.

Mutates ``ctx.config`` in place (matches
:func:`brain_core.config.writer.persist_config_or_revert`'s
field-by-field shape; ``ToolContext`` is frozen so we cannot reassign
``ctx.config`` and must field-mutate). Subsequent calls to
:func:`brain_core.tools.repair_config.handle` see the post-apply state and
report ``repair_changes_pending=False``.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.schema import Config
from brain_core.config.writer import save_config
from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_repair_config_apply"
DESCRIPTION = (
    "Apply the repaired config payload returned by brain_repair_config: "
    "validate via schema, persist to <vault>/.brain/config.json via "
    "save_config, and update ctx.config in-memory. Refuses payloads that "
    "fail schema validation."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repaired_config": {
            "type": "object",
            "description": (
                "The persisted_dict() payload returned by brain_repair_config "
                "in data.repaired_config. Round-tripped here so the frontend "
                "doesn't have to re-derive the repaired state."
            ),
        },
    },
    "required": ["repaired_config"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    """Validate ``arguments['repaired_config']`` and persist via save_config.

    Sequence:
      1. Validate the payload by constructing a fresh ``Config(**payload)``.
         Raises a Pydantic validation error if the payload is malformed —
         the disk write does not run.
      2. Mutate ``ctx.config`` in place to mirror the validated Config.
         Field-by-field setattr because ToolContext is frozen.
      3. Persist via ``save_config`` (atomic temp+rename, filelock-guarded,
         backup-on-write per Plan 11). On disk-write failure, in-memory
         mutation is NOT rolled back — the caller (frontend) re-fetches
         and the next ``brain_repair_config`` call surfaces the residual
         drift as a fresh diff.

    Returns a structured ``ToolResult`` with ``status: "applied"`` plus the
    persisted-dict shape that landed on disk for the UI to confirm against.
    """
    raise_if_no_config(ctx, NAME)

    if "repaired_config" not in arguments:
        raise ValueError(
            "brain_repair_config_apply requires 'repaired_config' in arguments"
        )
    payload = arguments["repaired_config"]
    if not isinstance(payload, dict):
        raise ValueError(
            f"'repaired_config' must be an object, got {type(payload).__name__}"
        )

    # Validate before any mutation. Pydantic will raise on malformed payloads;
    # we propagate the underlying error so the brain_api error envelope can
    # surface schema details to the UI (the dispatcher wraps ValueError /
    # ValidationError into a 400 ApiError automatically).
    validated = Config(**payload)

    # Plan 11 D4: ``vault_path`` is excluded from the persisted whitelist.
    # The ``Config(**payload)`` we just built has the schema default for
    # ``vault_path`` (since it's not in payload), but the live ``ctx.config``
    # was loaded against the real vault root — preserve that by carrying
    # the live ``vault_path`` forward into the mutation. This matches
    # the loader's normal behavior (env / setup wizard sources ``vault_path``,
    # never the persisted blob).
    live_vault = ctx.config.vault_path

    # Field-by-field in-place mutation (ToolContext is frozen — same shape
    # as ``persist_config_or_revert``). Mutate every model field on the
    # validated Config except ``vault_path`` (preserved from live).
    for field_name in type(ctx.config).model_fields:
        if field_name == "vault_path":
            continue
        setattr(ctx.config, field_name, getattr(validated, field_name))

    # Restore the live vault path in case the loop touched it (defensive;
    # the explicit skip above already guarantees this).
    ctx.config.vault_path = live_vault

    # Persist via save_config. The writer bumps ``config_version`` in
    # place + handles atomic write + backup. If this raises
    # ConfigPersistenceError, the in-memory mutation above stays —
    # acceptable per the docstring contract.
    written_path = save_config(ctx.config, ctx.vault_root)

    return ToolResult(
        text=f"applied repaired config to {written_path}",
        data={
            "status": "applied",
            "path": str(written_path),
            "config_version": ctx.config.config_version,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
