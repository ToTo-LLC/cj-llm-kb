"""brain_bulk_import — plan (or apply) a bulk import from a folder.

Wraps ``brain_core.ingest.bulk.BulkImporter``. Two phases:

  1. ``BulkImporter.plan(folder, allowed_domains=...)`` walks the folder, calls
     the classifier once per candidate file, and returns a ``BulkPlan`` without
     writing anything. This is the default (``dry_run=True``) behavior.

  2. ``BulkImporter.apply(plan, allowed_domains=...)`` runs the full
     ``IngestPipeline.ingest`` per item and returns a list of ``IngestResult``.
     Only reachable when the caller passes ``dry_run=False``.

Safety rails:
  - Default is ``dry_run=True`` (spec §7).
  - A ``dry_run=False`` call on a folder with more than 20 candidate files is
    refused unless the caller passes ``max_files`` — this check fires BEFORE
    any LLM work so an accidental bulk-apply can't burn tokens.
  - Rate-limit check fires before ``plan()`` using a rough ``tokens`` budget of
    1000 per candidate file (the classifier prompt is small; this overshoots
    deliberately so a refused call is cheap and deterministic).
  - Scope guard: ``allowed_domains=ctx.allowed_domains`` on both ``plan()`` and
    ``apply()`` — personal content never gets classified into a research
    session.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.ingest.bulk import BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_bulk_import"
DESCRIPTION = (
    "Plan (or apply) a bulk import from a folder of source files. Default is "
    "dry_run=True. Applying >20 files requires an explicit max_files cap to "
    "avoid accidental bulk LLM spend."
)

# Rough token cost per candidate file (classifier prompt + 256 max output).
# Multiplied by min(file_count, max_files) for the rate-limit pre-check.
_CLASSIFY_TOKEN_COST = 1000

# Apply is expensive (classify + summarize + integrate per file). Refuse if the
# folder has more than this many files and the caller did NOT pass max_files.
_LARGE_FOLDER_THRESHOLD = 20

# Model strings — must match brain_core.tools.ingest so both tools route through
# the same Anthropic models on real runs.
_CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
_SUMMARIZE_MODEL = "claude-sonnet-4-6"
_INTEGRATE_MODEL = "claude-sonnet-4-6"

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "folder": {
            "type": "string",
            "description": "Absolute path to the source folder.",
        },
        "dry_run": {
            "type": "boolean",
            "default": True,
            "description": (
                "When true (default), return a plan with per-file classification "
                "and do not write the vault. When false, run the full ingest "
                "pipeline per item — >20 files requires max_files."
            ),
        },
        "max_files": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Cap on the number of files to include in the plan/apply. "
                "Required for dry_run=False on folders with >20 files."
            ),
        },
    },
    "required": ["folder"],
}


def _build_pipeline(ctx: ToolContext) -> IngestPipeline:
    """Construct the IngestPipeline using the same shape as brain_ingest."""
    return IngestPipeline(
        vault_root=ctx.vault_root,
        writer=ctx.writer,
        llm=ctx.llm,
        summarize_model=_SUMMARIZE_MODEL,
        integrate_model=_INTEGRATE_MODEL,
        classify_model=_CLASSIFY_MODEL,
        state_db=ctx.state_db,
    )


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    folder = Path(str(arguments["folder"]))
    if not folder.exists() or not folder.is_dir():
        # Plain-English "next action" message per project principle (9).
        raise FileNotFoundError(f"folder not found: {folder}")

    dry_run = bool(arguments.get("dry_run", True))
    max_files_arg = arguments.get("max_files")
    max_files = int(max_files_arg) if max_files_arg is not None else None

    # ------------------------------------------------------------------
    # Pre-classify refusal: count candidate files and refuse heavy applies.
    # BulkImporter.plan() iterates ``folder.glob("**/*")``, skipping hidden
    # files, directories, and symlinks. We do the same count here with
    # ``rglob("*")`` so the threshold check matches what plan() would see.
    # ------------------------------------------------------------------
    files = [p for p in folder.rglob("*") if p.is_file() and not p.is_symlink()]
    file_count = len(files)

    if not dry_run and file_count > _LARGE_FOLDER_THRESHOLD and max_files is None:
        return ToolResult(
            text=f"refused: folder has {file_count} files (>{_LARGE_FOLDER_THRESHOLD})",
            data={
                "status": "refused",
                "reason": (f"bulk apply to {file_count} files requires explicit max_files cap"),
                "file_count": file_count,
            },
        )

    # Rate-limit check fires BEFORE plan() so a refused call is cheap and
    # deterministic. We budget one classifier call per file the plan() phase
    # would issue, capped at max_files if provided. Raises RateLimitError on
    # drain; transport/caller converts to the response shape.
    classify_count = min(file_count, max_files) if max_files is not None else file_count
    token_cost = _CLASSIFY_TOKEN_COST * max(classify_count, 1)
    ctx.rate_limiter.check("tokens", cost=token_cost)

    # ------------------------------------------------------------------
    # Plan phase — always run this (both dry_run and apply).
    # ------------------------------------------------------------------
    pipeline = _build_pipeline(ctx)
    importer = BulkImporter(pipeline)
    plan = await importer.plan(folder, allowed_domains=ctx.allowed_domains)

    # Respect max_files at the MCP layer: BulkPlan is a non-frozen dataclass,
    # so slicing items in place is safe. This truncates AFTER classify, but the
    # rate-limit pre-check already budgeted for the truncated count; the extra
    # classifier calls on overflow items are a tradeoff for the simpler API.
    if max_files is not None and len(plan.items) > max_files:
        plan.items = plan.items[:max_files]

    if dry_run:
        return ToolResult(
            text=f"planned {len(plan.items)} file(s)",
            data={
                "status": "planned",
                "file_count": len(plan.items),
                "skipped_count": len(plan.skipped),
                "items": [
                    {
                        "path": item.spec.as_posix(),
                        "slug": item.slug,
                        "classified_domain": item.classified_domain,
                        "confidence": item.confidence,
                    }
                    for item in plan.items
                ],
            },
        )

    # ------------------------------------------------------------------
    # Apply phase — reuse importer.apply() so the per-item IngestPipeline
    # invocation path is identical to the single-file brain_ingest tool.
    # ------------------------------------------------------------------
    results = await importer.apply(plan, allowed_domains=ctx.allowed_domains)

    applied: list[str] = []
    quarantined: list[str] = []
    duplicate: list[str] = []
    failed: list[dict[str, Any]] = []
    for item, result in zip(plan.items, results, strict=True):
        spec_str = item.spec.as_posix()
        if result.status is IngestStatus.OK:
            applied.append(spec_str)
        elif result.status is IngestStatus.QUARANTINED:
            quarantined.append(spec_str)
        elif result.status is IngestStatus.SKIPPED_DUPLICATE:
            duplicate.append(spec_str)
        else:  # FAILED
            failed.append({"path": spec_str, "errors": list(result.errors)})

    return ToolResult(
        text=(
            f"applied {len(applied)} file(s), {len(quarantined)} quarantined, "
            f"{len(duplicate)} duplicate, {len(failed)} failed"
        ),
        data={
            "status": "applied",
            "applied": applied,
            "quarantined": quarantined,
            "duplicate": duplicate,
            "failed": failed,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
