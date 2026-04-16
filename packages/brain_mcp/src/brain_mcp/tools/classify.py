"""brain_classify — classify content into a vault domain via the Plan 02 classifier.

Thin MCP wrapper around ``brain_core.ingest.classifier.classify``. The
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

from typing import Any

import mcp.types as types
from brain_core.ingest.classifier import classify

from brain_mcp.tools.base import ToolContext, text_result

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

# Model string MUST match brain_mcp.tools.ingest._INGEST_TOKEN_ESTIMATE's pipeline
# classify_model so both tools route through the same Anthropic model on real
# runs. Changes here need a matching change in ingest.py.
_CLASSIFY_MODEL = "claude-haiku-4-5-20251001"

# Rough token cost for one classify call (classify prompt + 256 max output).
# The fake LLM doesn't care; this is a rate-limit budget only.
_CLASSIFY_TOKEN_COST = 1000

# Max input length passed to the classifier. Matches the classify prompt's
# expected "snippet" size — the classifier already truncates, but we truncate
# earlier so the rate-limit bucket reflects what we actually spend.
_MAX_SNIPPET_CHARS = 2048


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    # Rate-limit check fires BEFORE any LLM work so refusals are cheap.
    if not ctx.rate_limiter.check("tokens", cost=_CLASSIFY_TOKEN_COST):
        return text_result(
            "rate limited (tokens/min)",
            data={"status": "rate_limited", "bucket": "tokens", "retry_after_seconds": 60},
        )

    content = str(arguments["content"])[:_MAX_SNIPPET_CHARS]
    hint_arg = arguments.get("hint")
    title = str(hint_arg) if hint_arg is not None else ""

    result = await classify(
        llm=ctx.llm,
        model=_CLASSIFY_MODEL,
        title=title,
        snippet=content,
    )

    # Sanitize: if the classifier returned an out-of-scope domain, don't leak
    # the classification. `reason` here is a tool-level string explaining the
    # scrub — it is NOT a passthrough from ClassifyResult (which has no such
    # field).
    if result.domain not in ctx.allowed_domains:
        return text_result(
            "(classification not in allowed scope)",
            data={
                "domain": "unknown",
                "confidence": 0.0,
                "reason": (
                    f"classifier returned {result.domain!r} which is not in "
                    f"allowed domains {ctx.allowed_domains}"
                ),
            },
        )

    return text_result(
        f"{result.domain} (confidence={result.confidence:.2f})",
        data={
            "domain": result.domain,
            "confidence": result.confidence,
            "source_type": result.source_type,
            "needs_user_pick": result.needs_user_pick,
        },
    )
