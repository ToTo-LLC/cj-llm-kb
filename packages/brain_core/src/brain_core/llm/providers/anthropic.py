"""AnthropicProvider — production LLMProvider implementation.

This is the ONLY module in the project that imports the `anthropic` SDK.
All other modules depend on `brain_core.llm.LLMProvider` (the Protocol).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from brain_core.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
    ToolUse,
    ToolUseStart,
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str, client: Any | None = None) -> None:
        if client is None:
            from anthropic import AsyncAnthropic  # imported lazily; tests inject via client=

            client = AsyncAnthropic(api_key=api_key)
        # Stored as Any so we can accept either a real AsyncAnthropic or a duck-typed
        # test stub without fighting the SDK's strict TypedDicts at the call sites.
        self._client: Any = client

    def _serialize_message(self, m: LLMMessage) -> dict[str, Any]:
        """Translate an LLMMessage to the SDK's expected shape."""
        if isinstance(m.content, str):
            return {"role": m.role, "content": m.content}
        blocks: list[dict[str, Any]] = []
        for block in m.content:
            if block.kind == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.kind == "tool_use":
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            elif block.kind == "tool_result":
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "content": block.content,
                        "is_error": block.is_error,
                    }
                )
        return {"role": m.role, "content": blocks}

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raw: Any = await self._client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[self._serialize_message(m) for m in request.messages],
            stop_sequences=request.stop_sequences or None,
            tools=[t.model_dump() for t in request.tools] if request.tools else None,
        )
        text_blocks: list[str] = []
        tool_uses: list[ToolUse] = []
        for block in raw.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_blocks.append(block.text)
            elif btype == "tool_use":
                tool_uses.append(
                    ToolUse(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=dict(getattr(block, "input", {})),
                    )
                )
        return LLMResponse(
            model=raw.model,
            content="".join(text_blocks),
            usage=TokenUsage(
                input_tokens=getattr(raw.usage, "input_tokens", 0),
                output_tokens=getattr(raw.usage, "output_tokens", 0),
            ),
            stop_reason=getattr(raw, "stop_reason", None),
            tool_uses=tool_uses,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        # Minimal async-iter bridge. Full streaming is tested live in Plan 02 contract tests.
        # For tool_use, we emit tool_use_start on content_block_start, tool_use_input_delta
        # on input_json_delta events, and rely on the session loop (Task 17) to accumulate
        # input deltas between tool_use_start markers.
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system or "",
            "messages": [self._serialize_message(m) for m in request.messages],
        }
        if request.tools:
            kwargs["tools"] = [t.model_dump() for t in request.tools]
        async with self._client.messages.stream(**kwargs) as s:
            async for event in s:
                ev_type = getattr(event, "type", "")
                if ev_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    btype = getattr(block, "type", "") if block else ""
                    if btype == "tool_use":
                        yield LLMStreamChunk(
                            tool_use_start=ToolUseStart(
                                id=getattr(block, "id", ""),
                                name=getattr(block, "name", ""),
                            )
                        )
                elif ev_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", "") if delta else ""
                    if dtype == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield LLMStreamChunk(delta=text)
                    elif dtype == "input_json_delta":
                        partial = getattr(delta, "partial_json", "")
                        if partial:
                            yield LLMStreamChunk(tool_use_input_delta=partial)
                else:
                    # Fallback: some stream events expose a `.delta.text` directly.
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
