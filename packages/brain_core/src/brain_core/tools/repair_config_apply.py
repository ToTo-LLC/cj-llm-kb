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

Plan 17 Task 17: the field-by-field mutation + persist is wrapped in
:func:`brain_core.config.writer.persist_config_or_revert` so a
``save_config`` failure (disk full, lock timeout, replace_failed) rolls
back the in-memory Config to its pre-mutation state. Pre-T17, the live
``ctx.config`` was left in the post-mutation "bad" state until the next
read; Plan 16 T34's lazy version-peek would self-heal eventually, but
the failure-window observability was wrong (callers saw the failed
mutation as success). The helper's snapshot-then-revert contract closes
the seam — same atomicity guarantee as the five Plan 11 T4 mutation
tools (``brain_config_set``, ``brain_create_domain``, etc.).
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.schema import Config
from brain_core.config.writer import persist_config_or_revert
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
      2. Inside ``persist_config_or_revert`` (snapshot, yield, save, revert):
         mutate ``ctx.config`` field-by-field to mirror the validated
         Config. The helper persists via ``save_config`` after the yield;
         any failure (caller mutation, schema cross-field validators,
         lock timeout, disk write) restores the snapshot's field values
         and re-raises so the caller observes structured error +
         pre-mutation in-memory state.

    Returns a structured ``ToolResult`` with ``status: "applied"`` plus the
    persisted-dict shape that landed on disk for the UI to confirm against.

    Plan 17 Task 17: the mutation+save pair is wrapped in
    ``persist_config_or_revert`` so a ``save_config`` failure rolls back
    the live ``ctx.config`` atomically. Pre-T17 the helper was not used
    and a disk-write failure left the live Config in the post-mutation
    state — observable as a phantom successful apply until the next read.
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
    # ValidationError into a 400 ApiError automatically). This runs OUTSIDE
    # the persist_config_or_revert block because a malformed payload should
    # never even reach the snapshot — no mutation to revert.
    validated = Config(**payload)

    # Plan 11 D4: ``vault_path`` is excluded from the persisted whitelist.
    # The ``Config(**payload)`` we just built has the schema default for
    # ``vault_path`` (since it's not in payload), but the live ``ctx.config``
    # was loaded against the real vault root — preserve that by carrying
    # the live ``vault_path`` forward into the mutation. This matches
    # the loader's normal behavior (env / setup wizard sources ``vault_path``,
    # never the persisted blob).
    live_vault = ctx.config.vault_path

    # Plan 17 Task 17: mutate + persist inside the snapshot/revert helper.
    # Same shape as the Plan 11 T4 mutation tools (config_set, create_domain,
    # rename_domain, delete_domain, budget_override). The helper snapshots
    # ``ctx.config`` before the yield, lets us mutate field-by-field
    # (ToolContext is frozen so we cannot reassign), then calls save_config
    # on the live reference. On any exception between snapshot and a
    # successful disk replace, ``persist_config_or_revert`` restores every
    # field via the ``__dict__`` fast-path (Plan 16 T36 — bypasses
    # validate_assignment so transient cross-field invalid intermediates
    # don't fault the revert) and re-raises.
    with persist_config_or_revert(ctx.config, ctx.vault_root):
        for field_name in type(ctx.config).model_fields:
            if field_name == "vault_path":
                continue
            setattr(ctx.config, field_name, getattr(validated, field_name))
        # Restore the live vault path defensively (the explicit skip above
        # already guarantees this).
        ctx.config.vault_path = live_vault

    # ``save_config`` ran inside the helper; reconstruct the written path
    # from the canonical location. (We don't capture the helper's return
    # because the context manager interface doesn't surface it; the path
    # is deterministic — ``<vault_root>/.brain/config.json``.)
    written_path = ctx.vault_root / ".brain" / "config.json"

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
