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

from pathlib import Path
from typing import Any

import mcp.types as types
from brain_core.chat.types import ChatMode
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.vault.paths import ScopeError

from brain_mcp.tools.base import ToolContext, text_result

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


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    # ------------------------------------------------------------------
    # Rate-limit checks — fire BEFORE any pipeline work so a refused call
    # is cheap and deterministic.
    # ------------------------------------------------------------------
    if not ctx.rate_limiter.check("patches", cost=1):
        return text_result(
            "rate limited (patches/min)",
            data={"status": "rate_limited", "bucket": "patches", "retry_after_seconds": 60},
        )
    if not ctx.rate_limiter.check("tokens", cost=_INGEST_TOKEN_ESTIMATE):
        return text_result(
            "rate limited (tokens/min)",
            data={"status": "rate_limited", "bucket": "tokens", "retry_after_seconds": 60},
        )

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

    pipeline = IngestPipeline(
        vault_root=ctx.vault_root,
        writer=ctx.writer,
        llm=ctx.llm,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )

    result = await pipeline.ingest(
        spec,
        allowed_domains=ctx.allowed_domains,
        domain_override=domain_override,
        apply=autonomous,
    )

    # Non-OK paths: surface the pipeline's status verbatim.
    if result.status is not IngestStatus.OK:
        return text_result(
            f"ingest status: {result.status.value}",
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
        return text_result(
            f"ingested {note_path}",
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
    target_path = patchset.new_files[0].path if patchset.new_files else note_path
    # Truncate the `source` preview inside the reason so long raw-text blobs
    # don't blow up the envelope JSON.
    reason = patchset.reason or f"ingested via brain_ingest from {source_arg[:100]}"
    envelope = ctx.pending_store.put(
        patchset=patchset,
        source_thread="mcp-ingest",
        # ChatMode.BRAINSTORM is the closest semantic match for "staged for
        # human approval". A dedicated ChatMode.INGEST value is deferred to
        # the Task 25 sweep; accept the convenience mapping for now.
        mode=ChatMode.BRAINSTORM,
        tool="brain_ingest",
        target_path=target_path,
        reason=reason,
    )
    return text_result(
        f"staged patch {envelope.patch_id}",
        data={
            "status": "pending",
            "patch_id": envelope.patch_id,
            "target_path": str(envelope.target_path),
        },
    )
