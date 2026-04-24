"""brain_ingest — run the Plan 02 ingest pipeline, stage or apply the result.

By default ``brain_ingest`` stages the PatchSet the pipeline produces via
``ctx.pending_store`` for human approval — matching the approval-gated flow
used everywhere else in brain. Pass ``autonomous=true`` to apply immediately
through ``ctx.writer`` (also via the pipeline's Stage 9 apply path).

Rate limits (per spec §7) fire before any pipeline work: a ``patches`` bucket
decrement (cost=1) plus a ``tokens`` bucket decrement with a rough estimate
for the ~3 LLM calls the pipeline makes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.chat.types import ChatMode
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError
from brain_core.vault.types import PatchCategory

NAME = "brain_ingest"
DESCRIPTION = (
    "Ingest a source (URL, absolute file path, or raw text) into the vault "
    "via the summarize+classify+integrate pipeline. Default: stage the "
    "resulting PatchSet for human approval. Pass `autonomous=true` to apply "
    "immediately."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source": {
            "type": "string",
            "description": "URL, absolute file path, or raw text content.",
        },
        "autonomous": {
            "type": "boolean",
            "default": False,
            "description": "When true, apply the PatchSet immediately via VaultWriter.",
        },
        "domain_override": {
            "type": "string",
            "description": "Skip classify and force this domain (must be in allowed_domains).",
        },
    },
    "required": ["source"],
}

# Rough token estimate for one ingest run (classify + summarize + integrate).
_INGEST_TOKEN_ESTIMATE = 8000


# Fallbacks when ``ToolContext.config`` is None (issue #31). Keep in sync
# with the LLMConfig defaults so a None-config pipeline behaves identically
# to a default-LLMConfig pipeline.
_SUMMARIZE_MODEL_FALLBACK = "claude-sonnet-4-6"
_INTEGRATE_MODEL_FALLBACK = "claude-sonnet-4-6"
_CLASSIFY_MODEL_FALLBACK = "claude-haiku-4-5-20251001"


def _build_pipeline_from_ctx(ctx: ToolContext) -> IngestPipeline:
    """Construct the IngestPipeline using the ctx primitives.

    Resolves model strings from ``ctx.config.llm`` (LLMConfig) when present,
    falling back to the hardcoded constants when no config is wired (issue
    #31). The fallback path keeps the 56+ existing ToolContext construction
    sites that don't pass a config working unchanged.

    Issue #23: also resolves the source-handler list from
    ``ctx.config.handlers`` so per-handler tunables (URL/Tweet timeouts,
    PDF min_chars) take effect.
    """
    from brain_core.ingest.dispatcher import _default_handlers

    cfg_llm = getattr(ctx.config, "llm", None) if ctx.config is not None else None
    cfg_handlers = (
        getattr(ctx.config, "handlers", None) if ctx.config is not None else None
    )
    classify_model = (
        getattr(cfg_llm, "classify_model", None) or _CLASSIFY_MODEL_FALLBACK
    )
    # ``default_model`` covers both summarize and integrate today (the spec
    # treats both as Sonnet-class). When/if the schema grows separate
    # summarize_model / integrate_model fields, this is the single point to
    # update.
    summarize_model = (
        getattr(cfg_llm, "default_model", None) or _SUMMARIZE_MODEL_FALLBACK
    )
    integrate_model = (
        getattr(cfg_llm, "default_model", None) or _INTEGRATE_MODEL_FALLBACK
    )
    # Pass the resolved handler list only when a config was supplied;
    # otherwise leave it None so the pipeline falls back to the hardcoded
    # defaults (which is what the no-config tests expect).
    handlers = _default_handlers(cfg_handlers) if cfg_handlers is not None else None
    return IngestPipeline(
        vault_root=ctx.vault_root,
        writer=ctx.writer,
        llm=ctx.llm,
        summarize_model=summarize_model,
        integrate_model=integrate_model,
        classify_model=classify_model,
        state_db=ctx.state_db,
        handlers=handlers,
    )


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    # ------------------------------------------------------------------
    # Rate-limit checks — fire BEFORE any pipeline work so a refused call
    # is cheap and deterministic. Both checks raise RateLimitError on drain;
    # transport shims (brain_mcp) or exception handlers (brain_api) convert
    # the exception into their response shape.
    # ------------------------------------------------------------------
    ctx.rate_limiter.check("patches", cost=1)
    ctx.rate_limiter.check("tokens", cost=_INGEST_TOKEN_ESTIMATE)

    source_arg = str(arguments["source"])
    autonomous = bool(arguments.get("autonomous", False))
    domain_override_arg = arguments.get("domain_override")
    domain_override = str(domain_override_arg) if domain_override_arg is not None else None

    # Scope-check domain_override before spending any LLM tokens.
    if domain_override is not None and domain_override not in ctx.allowed_domains:
        raise ScopeError(
            f"domain_override {domain_override!r} not in allowed {ctx.allowed_domains}"
        )

    # Route the source argument: absolute path → Path (handled by TextHandler,
    # PDFHandler, etc.); otherwise leave as str (URL / raw text).
    as_path = Path(source_arg)
    spec: str | Path = as_path if as_path.is_absolute() and as_path.exists() else source_arg

    pipeline = _build_pipeline_from_ctx(ctx)

    result = await pipeline.ingest(
        spec,
        allowed_domains=ctx.allowed_domains,
        domain_override=domain_override,
        apply=autonomous,
    )

    # Non-OK paths: surface the pipeline's status verbatim.
    if result.status is not IngestStatus.OK:
        return ToolResult(
            text=f"ingest status: {result.status.value}",
            data={
                "status": result.status.value,
                "errors": list(result.errors),
                "note_path": str(result.note_path) if result.note_path else None,
            },
        )

    # OK + autonomous: vault has been written by the pipeline's Stage 9.
    if autonomous:
        # note_path is always set on a successful apply=True run.
        note_path = result.note_path
        assert note_path is not None  # mypy narrowing; IngestStatus.OK ⇒ path set
        return ToolResult(
            text=f"ingested {note_path}",
            data={
                "status": "applied",
                "note_path": str(note_path),
            },
        )

    # OK + staged: patchset is populated, vault is untouched.
    patchset = result.patchset
    note_path = result.note_path
    assert patchset is not None  # mypy narrowing; apply=False + OK ⇒ patchset set
    assert note_path is not None
    # Plan 07 Task 1: stamp the INGEST category so the autonomy gate in
    # brain_apply_patch can opt this patch into auto-apply when the user
    # has set ``autonomous.ingest = true``. The pipeline itself stays
    # category-agnostic (default OTHER) — the tool layer is where the
    # semantic label lives.
    patchset.category = PatchCategory.INGEST
    target_path = patchset.new_files[0].path if patchset.new_files else note_path
    # Truncate the `source` preview inside the reason so long raw-text blobs
    # don't blow up the envelope JSON.
    reason = patchset.reason or f"ingested via brain_ingest from {source_arg[:100]}"
    envelope = ctx.pending_store.put(
        patchset=patchset,
        source_thread="mcp-ingest",
        # MCP-origin tag — distinguishes ingest-origin pending patches from
        # chat-origin ones in the patch-queue UI (issue #30).
        mode=ChatMode.MCP,
        tool="brain_ingest",
        target_path=target_path,
        reason=reason,
    )
    return ToolResult(
        text=f"staged patch {envelope.patch_id}",
        data={
            "status": "pending",
            "patch_id": envelope.patch_id,
            "target_path": str(envelope.target_path),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
