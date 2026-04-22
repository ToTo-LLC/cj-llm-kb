"""brain_ping_llm — 1-token round-trip against the configured LLM provider.

Backend for the Settings → "Test connection" button. Issues a tiny
``complete`` call via ``ctx.llm`` and records the round-trip latency in
milliseconds. Failures surface as ``ok=False`` with the exception text
rather than propagating — the UI needs a stable envelope to render.

Deliberately NOT rate-limited: the user is explicitly asking to probe
the provider, and a 1-token call is cheap enough that the existing
daily budget is the right cost control. The cost ledger still records
the spend (the provider hook handles that), so a misconfigured provider
that returns a large response cannot run up unbounded cost.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_ping_llm"
DESCRIPTION = (
    "Send a 1-token probe to the configured LLM provider. Returns ok / "
    "latency_ms / provider / model, or an error string on failure. "
    "Used by the Settings 'Test connection' button."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "model": {
            "type": "string",
            "description": "Override the provider's default model for this probe.",
        },
    },
}


_DEFAULT_MODEL = "claude-haiku-4-6"


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    if ctx.llm is None:
        return ToolResult(
            text="ping_llm failed: no LLM provider configured on the ToolContext",
            data={
                "ok": False,
                "error": "no LLM provider configured",
                "provider": None,
                "model": None,
                "latency_ms": 0,
            },
        )
    model = str(arguments.get("model") or _DEFAULT_MODEL)
    request = LLMRequest(
        model=model,
        messages=[LLMMessage(role="user", content="ok")],
        max_tokens=1,
        temperature=0.0,
    )
    provider_name = getattr(ctx.llm, "name", "unknown")

    start = time.monotonic()
    try:
        response = await ctx.llm.complete(request)
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return ToolResult(
            text=f"ping_llm failed: {exc}",
            data={
                "ok": False,
                "error": str(exc),
                "provider": provider_name,
                "model": model,
                "latency_ms": latency_ms,
            },
        )
    latency_ms = int((time.monotonic() - start) * 1000)
    return ToolResult(
        text=(
            f"ping_llm ok: provider={provider_name}, model={response.model}, "
            f"latency_ms={latency_ms}"
        ),
        data={
            "ok": True,
            "provider": provider_name,
            "model": response.model,
            "latency_ms": latency_ms,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
