"""brain_watch_folder — add a folder to Config.watched_folders + initial sync.

Plan 22 T5. Validates the folder, appends a
:class:`brain_core.config.schema.WatchedFolder` to
:attr:`Config.watched_folders`, optionally triggers a pre-sync backup,
and (when ``initial_sync=True``) calls
:meth:`brain_core.ingest.bulk.BulkImporter.plan` /
:meth:`brain_core.ingest.bulk.BulkImporter.apply` against the folder.

**Cross-field invariant**: when ``domain`` is provided, the slug MUST
exist in :attr:`Config.domains` BEFORE the append. Per Plan 16 T36, a
Pydantic ``model_validator(mode="after")`` raise under
``validate_assignment=True`` leaves the field MUTATED to the bad value
even after the raise; the canonical workaround
(:func:`brain_core.tools.config_set._check_active_domain_membership`)
is a pre-check that runs BEFORE the mutation. The same pattern applies
here for ``watched_folders``: pre-check the slug, then append.

**Backup trigger**: pre-sync backup uses
``trigger="pre_watched_folder_sync"`` so the Settings page can group
these snapshots distinctly from manual / daily / bulk-import backups.
Wrapped in a narrow ``try/except`` — backup is best-effort here; the
watch was already registered before the backup attempt, so a backup
failure must not block the user's opt-in sync.

**Initial-sync cost estimate (Plan 22 D3)**: BEFORE invoking
``BulkImporter`` for the initial sync, this tool computes
``estimated_tokens = file_count × _CLASSIFY_TOKEN_COST`` (mirrors
``bulk_import.py``'s pre-check budget) and surfaces an informational
USD estimate in both ``ToolResult.text`` and ``ToolResult.data``.
The estimate is informational only — there is NO refusal threshold
per D3. The existing rate-limit + per-domain budget caps (Plan 16
T26-T32) remain the hard ceilings: if a sync would blow them, those
checks fire mid-sync and refuse.

**Idempotent on already-watched**: if the folder already appears in
``Config.watched_folders``, return ``status="already_watched"`` without
re-running the initial sync (cheap re-call is safe).

**Lazy classify**: when ``domain`` is ``None`` and ``initial_sync=True``,
``BulkImporter.plan()`` calls the classifier per file (its normal
behavior). The plan-doc's "defer classify decision to first file event"
applies to the watcher path (T6); for the initial sync, classifying
per-file in bulk is the closest equivalent — the classifier picks a
domain in ``allowed_domains`` and the per-item ``domain_override`` flows
from the BulkPlan, not from ``WatchedFolder.domain``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.backup import create_snapshot
from brain_core.budget import PerDomainBudgetGuard
from brain_core.config.schema import WatchedFolder
from brain_core.config.writer import persist_config_or_revert
from brain_core.cost.budget import BudgetEnforcer
from brain_core.ingest.bulk import BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm import resolve_llm_config
from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_watch_folder"
DESCRIPTION = (
    "Add a folder to Config.watched_folders and optionally run an initial "
    "sync via BulkImporter. domain=None defers classification to per-file. "
    "Idempotent: already-watched returns status='already_watched'."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "folder": {
            "type": "string",
            "description": "Absolute path of the folder to watch.",
        },
        "domain": {
            "type": ["string", "null"],
            "description": (
                "Target domain slug. None defers classification to the "
                "BulkImporter classifier on each file."
            ),
        },
        "include_subdirs": {
            "type": "boolean",
            "default": True,
        },
        "initial_sync": {
            "type": "boolean",
            "default": True,
            "description": (
                "When true, run a full BulkImporter plan + apply pass against "
                "the folder immediately after watch is registered."
            ),
        },
    },
    "required": ["folder"],
}

# Fallback models used when ``ctx.config.llm`` is not present (issue #31
# / bulk_import.py precedent). Production paths always thread Config in.
_CLASSIFY_MODEL_FALLBACK = "claude-haiku-4-5-20251001"
_SUMMARIZE_MODEL_FALLBACK = "claude-sonnet-4-6"
_INTEGRATE_MODEL_FALLBACK = "claude-sonnet-4-6"

# Rough token cost per candidate file for the initial-sync cost estimate.
# Mirrors ``bulk_import.py:_CLASSIFY_TOKEN_COST`` so both tools project
# the same per-file classifier spend. Output tokens budgeted at the
# classifier's 256-token max so the estimate is a conservative ceiling
# for the classify-only stage. Summarize + integrate costs accrue per
# successfully-classified file post-classify and are not included.
_CLASSIFY_TOKEN_COST = 1000
_CLASSIFY_MAX_OUTPUT_TOKENS = 256


def _build_pipeline(ctx: ToolContext) -> IngestPipeline:
    """Mirror :func:`brain_core.tools.bulk_import._build_pipeline`.

    Routes model selection through :func:`resolve_llm_config` and
    falls back to the hardcoded constants when ``ctx.config`` /
    ``ctx.config.llm`` is missing.
    """
    from brain_core.ingest.dispatcher import _default_handlers

    cfg = ctx.config
    cfg_llm = resolve_llm_config(cfg, None) if cfg is not None else None
    cfg_handlers = getattr(cfg, "handlers", None) if cfg is not None else None
    classify_model = (
        getattr(cfg_llm, "classify_model", None) or _CLASSIFY_MODEL_FALLBACK
    )
    summarize_model = (
        getattr(cfg_llm, "default_model", None) or _SUMMARIZE_MODEL_FALLBACK
    )
    integrate_model = (
        getattr(cfg_llm, "default_model", None) or _INTEGRATE_MODEL_FALLBACK
    )
    handlers = (
        _default_handlers(cfg_handlers) if cfg_handlers is not None else None
    )
    guard = (
        PerDomainBudgetGuard(ctx.cost_ledger) if ctx.cost_ledger is not None else None
    )
    return IngestPipeline(
        vault_root=ctx.vault_root,
        writer=ctx.writer,
        llm=ctx.llm,
        summarize_model=summarize_model,
        integrate_model=integrate_model,
        classify_model=classify_model,
        state_db=ctx.state_db,
        handlers=handlers,
        guard=guard,
        config=cfg,
    )


def _estimate_initial_sync_cost(
    folder: Path, classify_model: str
) -> tuple[int, int, float | None]:
    """Compute an informational cost estimate for the initial sync.

    Returns ``(file_count, estimated_tokens, estimated_usd)`` where
    ``estimated_usd`` is ``None`` when the classify model has no pricing
    entry in ``brain_core.cost.budget._PRICING`` (forward-compat for a
    model swap that lands ahead of pricing). file_count is computed the
    same way ``BulkImporter.plan`` walks the folder so the estimate
    matches what the plan phase will actually classify.

    Per Plan 22 D3, this estimate is informational only — there is no
    refusal threshold. The rate-limit and per-domain budget guards
    elsewhere in the pipeline remain the hard ceilings.
    """
    files = [p for p in folder.rglob("*") if p.is_file() and not p.is_symlink()]
    file_count = len(files)
    estimated_tokens = file_count * _CLASSIFY_TOKEN_COST
    try:
        estimated_usd: float | None = BudgetEnforcer.estimate_cost(
            model=classify_model,
            input_tokens=estimated_tokens,
            output_tokens=file_count * _CLASSIFY_MAX_OUTPUT_TOKENS,
        )
    except KeyError:
        # No pricing entry for the configured classify model.
        # Surface the token count and let the caller display "n/a".
        estimated_usd = None
    return file_count, estimated_tokens, estimated_usd


def _check_domain_membership(domain: str, configured_domains: list[str]) -> None:
    """Mirror :func:`config_set._check_active_domain_membership` for watched_folders.

    Plan 16 T36 lesson: a ``model_validator(mode="after")`` raise under
    ``validate_assignment=True`` leaves the field mutated to the bad
    value. The cross-field validator
    ``Config._check_watched_folders_domains_in_domains`` (Plan 22 T1)
    enforces "every ``WatchedFolder.domain`` must be in ``Config.domains``"
    on construction, but a single-field setattr that appends a bad entry
    leaks past the rollback. The pre-check below runs BEFORE the
    mutation so the orphan-domain entry never lands on the live Config.
    """
    if domain not in configured_domains:
        raise ValueError(
            f"watched_folders entry references domain {domain!r} "
            f"that is not in domains {configured_domains!r}; "
            "add the domain first."
        )


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    folder_str = str(arguments["folder"])
    folder = Path(folder_str)
    domain_arg = arguments.get("domain")
    domain: str | None = str(domain_arg) if domain_arg is not None else None
    include_subdirs = bool(arguments.get("include_subdirs", True))
    initial_sync = bool(arguments.get("initial_sync", True))

    # Folder validation — checked before any config touch so a missing
    # folder fails fast (and a typo on Settings doesn't pollute config.json).
    if not folder.is_absolute():
        raise ValueError(
            f"folder path must be absolute, got {folder_str!r}"
        )
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"folder not found: {folder_str}")

    raise_if_no_config(ctx, "brain_watch_folder")
    cfg = ctx.config

    # Idempotency: already-watched is a status, not an error.
    for wf in cfg.watched_folders:
        if wf.path == folder_str:
            return ToolResult(
                text=f"folder {folder_str} is already watched",
                data={
                    "status": "already_watched",
                    "folder": folder_str,
                    "domain": wf.domain,
                    "initial_sync_summary": None,
                    # Cost estimate is None on the already_watched path —
                    # no initial sync runs, so there is no spend to
                    # project. Symmetric with the data shape on the
                    # ``watched`` + ``initial_sync=False`` path.
                    "cost_estimate": None,
                },
            )

    # Pre-check cross-field invariant when domain is supplied. When
    # ``domain`` is None the lazy-classify path applies — defer the slug
    # check to per-file classification, where every classified slug is
    # constrained to ``ctx.allowed_domains`` (which is a subset of
    # ``cfg.domains``).
    effective_domain = domain if domain is not None else "personal"
    if domain is not None:
        _check_domain_membership(domain, list(cfg.domains))
    else:
        # Lazy-classify mode: pick a stable placeholder slug to land on
        # the WatchedFolder record. We use the first non-personal
        # configured domain (or personal as last resort) so the record's
        # `domain` field is always a real slug — the per-file classifier
        # is the actual decider for the initial sync.
        effective_domain = next(
            (s for s in cfg.domains if s != "personal"),
            cfg.active_domain,
        )

    # Append the WatchedFolder INSIDE persist_config_or_revert so any
    # construction-time failure (e.g. the field-validator on path or
    # domain) is snapshot-revertible.
    new_wf = WatchedFolder(
        path=folder_str,
        domain=effective_domain,
        enabled=True,
        last_sync=None,
        policy="overwrite",
        include_subdirs=include_subdirs,
    )
    with persist_config_or_revert(cfg, ctx.vault_root):
        cfg.watched_folders.append(new_wf)

    initial_sync_summary: dict[str, Any] | None = None
    cost_estimate: dict[str, Any] | None = None
    if initial_sync:
        # Cost estimate fires BEFORE the backup + plan/apply so the user
        # sees the projected classify-only spend on the ToolResult. Per
        # Plan 22 D3 this is informational only — NO refusal threshold.
        # The classify model resolves the same way ``_build_pipeline``
        # picks it, so the estimate matches what the bulk import will
        # actually call.
        cfg_llm = (
            resolve_llm_config(cfg, None) if cfg is not None else None
        )
        classify_model = (
            getattr(cfg_llm, "classify_model", None)
            or _CLASSIFY_MODEL_FALLBACK
        )
        (
            estimate_file_count,
            estimated_tokens,
            estimated_usd,
        ) = _estimate_initial_sync_cost(folder, classify_model)
        cost_estimate = {
            "file_count": estimate_file_count,
            "estimated_tokens": estimated_tokens,
            "estimated_usd": estimated_usd,
            "classify_model": classify_model,
        }

        # Pre-sync backup with the distinct trigger so the Settings page
        # can group "pre-watched-folder-sync" snapshots separately from
        # manual / daily / pre-bulk-import. Wrapped in try/except so a
        # backup failure doesn't block the sync — the user explicitly
        # opted in to the watch + sync flow; backup is a best-effort
        # safety net here, not a hard rail.
        try:
            create_snapshot(ctx.vault_root, trigger="pre_watched_folder_sync")
        except (FileNotFoundError, ValueError):
            # vault_root missing OR pricing/trigger drift — surface
            # neither as a sync blocker. The watch was already
            # registered above.
            pass

        # Build pipeline + plan + apply. Pass domain_override only when
        # the user picked a specific domain; otherwise let the per-file
        # classifier decide.
        pipeline = _build_pipeline(ctx)
        importer = BulkImporter(pipeline)
        plan = await importer.plan(
            folder,
            allowed_domains=ctx.allowed_domains,
            domain_override=domain,
        )
        results = await importer.apply(
            plan,
            allowed_domains=ctx.allowed_domains,
            domain_override=domain,
        )

        applied = sum(1 for r in results if r.status is IngestStatus.OK)
        duplicate = sum(
            1 for r in results if r.status is IngestStatus.SKIPPED_DUPLICATE
        )
        failed = sum(1 for r in results if r.status is IngestStatus.FAILED)
        # Quarantined items count as "skipped" for the summary — the user
        # sees the count without having to disambiguate ingest internals.
        skipped_duplicate = duplicate
        initial_sync_summary = {
            "planned": len(plan.items),
            "applied": applied,
            "skipped_duplicate": skipped_duplicate,
            "failed": failed,
        }

    if cost_estimate is not None:
        if cost_estimate["estimated_usd"] is not None:
            usd_str = f"${cost_estimate['estimated_usd']:.4f}"
        else:
            usd_str = "n/a (no pricing entry)"
        cost_text = (
            f" | initial sync estimate: ~{cost_estimate['file_count']} files, "
            f"~{usd_str} (classify only; summarize+integrate cost is "
            f"per-file post-classify)"
        )
    else:
        cost_text = ""

    return ToolResult(
        text=(
            f"watched {folder_str} → {effective_domain}"
            + (
                f" (synced {initial_sync_summary['applied']}/"
                f"{initial_sync_summary['planned']} files)"
                if initial_sync_summary is not None
                else ""
            )
            + cost_text
        ),
        data={
            "status": "watched",
            "folder": folder_str,
            "domain": effective_domain,
            "initial_sync_summary": initial_sync_summary,
            "cost_estimate": cost_estimate,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
