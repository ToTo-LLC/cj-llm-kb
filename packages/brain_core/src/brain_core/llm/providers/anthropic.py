"""AnthropicProvider — production LLMProvider implementation.

This is the ONLY module in the project that imports the `anthropic` SDK.
All other modules depend on `brain_core.llm.LLMProvider` (the Protocol).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str, client: Any | None = None) -> None:
        if client is None:
            from anthropic import AsyncAnthropic  # imported lazily; tests inject via client=

            client = AsyncAnthropic(api_key=api_key)
        # Stored as Any so we can accept either a real AsyncAnthropic or a duck-typed
        # test stub without fighting the SDK's strict TypedDicts at the call sites.
        self._client: Any = client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raw: Any = await self._client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            stop_sequences=request.stop_sequences or None,
        )
        text = "".join(
            block.text for block in raw.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            model=raw.model,
            content=text,
            usage=TokenUsage(
                input_tokens=getattr(raw.usage, "input_tokens", 0),
                output_tokens=getattr(raw.usage, "output_tokens", 0),
            ),
            stop_reason=getattr(raw, "stop_reason", None),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        # Minimal async-iter bridge. Full streaming is tested live in Plan 02 contract tests.
        async with self._client.messages.stream(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
        ) as s:
            async for event in s:
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", "") if delta else ""
                if text:
                    yield LLMStreamChunk(delta=text)
            final = await s.get_final_message()
            yield LLMStreamChunk(
                usage=TokenUsage(
                    input_tokens=getattr(final.usage, "input_tokens", 0),
                    output_tokens=getattr(final.usage, "output_tokens", 0),
                ),
                done=True,
            )
