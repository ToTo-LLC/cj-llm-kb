"""brain_classify — classify content into a vault domain via the Plan 02 classifier.

Thin wrapper around ``brain_core.ingest.classifier.classify``. The
classifier itself makes exactly one LLM call (classify prompt), so this tool
consumes from the ``tokens`` bucket only. No ``patches`` bucket consumption —
classification produces a decision, not a PatchSet.

Scope sanitization: if the classifier returns a domain that isn't in
``ctx.allowed_domains`` (e.g. ``personal`` from a research-scoped session),
we scrub the result to ``{"domain": "unknown", "confidence": 0.0, ...}`` and
emit a tool-level ``reason`` explaining why. The underlying ClassifyResult is
NOT leaked to the caller.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.ingest.classifier import classify
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_classify"
DESCRIPTION = (
    "Classify a chunk of content into one of the user's vault domains. "
    "Returns {domain, confidence, source_type, needs_user_pick}. Out-of-scope "
    "classifications are sanitized to domain='unknown'."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "Content to classify (first ~2KB is used).",
        },
        "hint": {
            "type": "string",
            "description": "Optional hint about the source (title/URL/filename).",
        },
    },
    "required": ["content"],
}

# Fallback when ``ToolContext.config`` is None (issue #31). Both this and
# brain_core.tools.ingest read from ``ctx.config.llm.classify_model`` when a
# config is present, so swapping models is a single config field flip.
# Keep this string in sync with ``LLMConfig.classify_model`` default.
_CLASSIFY_MODEL_FALLBACK = "claude-haiku-4-5-20251001"


def _classify_model_for(ctx: ToolContext) -> str:
    """Resolve the classify model name from config, with fallback (issue #31)."""
    cfg = ctx.config
    if cfg is not None and getattr(cfg, "llm", None) is not None:
        model = getattr(cfg.llm, "classify_model", None)
        if model:
            return str(model)
    return _CLASSIFY_MODEL_FALLBACK


# Rough token cost for one classify call (classify prompt + 256 max output).
# The fake LLM doesn't care; this is a rate-limit budget only.
_CLASSIFY_TOKEN_COST = 1000

# Max input length passed to the classifier. Matches the classify prompt's
# expected "snippet" size — the classifier already truncates, but we truncate
# earlier so the rate-limit bucket reflects what we actually spend.
_MAX_SNIPPET_CHARS = 2048


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    # Rate-limit check fires BEFORE any LLM work so refusals are cheap.
    # Raises RateLimitError on drain; transport/caller converts.
    ctx.rate_limiter.check("tokens", cost=_CLASSIFY_TOKEN_COST)

    content = str(arguments["content"])[:_MAX_SNIPPET_CHARS]
    hint_arg = arguments.get("hint")
    title = str(hint_arg) if hint_arg is not None else ""

    result = await classify(
        llm=ctx.llm,
        model=_classify_model_for(ctx),
        title=title,
        snippet=content,
        # Plan 10 D6/Task 4: forward the call's allowed_domains so the
        # classify prompt's enum matches the scope the user is asking
        # about. Without this, the prompt would advertise the v0.1
        # default {research, work, personal} regardless of whether the
        # user added or removed domains via Settings → Domains.
        allowed_domains=ctx.allowed_domains,
    )

    # Sanitize: if the classifier returned an out-of-scope domain, don't leak
    # the classification. `reason` here is a tool-level string explaining the
    # scrub — it is NOT a passthrough from ClassifyResult (which has no such
    # field).
    if result.domain not in ctx.allowed_domains:
        return ToolResult(
            text="(classification not in allowed scope)",
            data={
                "domain": "unknown",
                "confidence": 0.0,
                "reason": (
                    f"classifier returned {result.domain!r} which is not in "
                    f"allowed domains {ctx.allowed_domains}"
                ),
            },
        )

    return ToolResult(
        text=f"{result.domain} (confidence={result.confidence:.2f})",
        data={
            "domain": result.domain,
            "confidence": result.confidence,
            "source_type": result.source_type,
            "needs_user_pick": result.needs_user_pick,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
