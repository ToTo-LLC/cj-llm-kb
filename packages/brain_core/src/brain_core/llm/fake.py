"""FakeLLMProvider — queue-based stub for tests. No network calls ever."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from brain_core.llm.types import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
    ToolUse,
    ToolUseStart,
)


@dataclass
class _QueuedResponse:
    content: str
    input_tokens: int
    output_tokens: int
    tool_uses: list[ToolUse] = field(default_factory=list)
    stop_reason: str = "end_turn"


class FakeLLMProvider:
    name = "fake"

    def __init__(self) -> None:
        self._queue: list[_QueuedResponse] = []
        self.requests: list[LLMRequest] = []

    def queue(self, content: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Queue a plain-text response (Plan 02 shape; stop_reason='end_turn')."""
        self._queue.append(
            _QueuedResponse(content=content, input_tokens=input_tokens, output_tokens=output_tokens)
        )

    def queue_tool_use(
        self,
        tool_uses: list[ToolUse],
        *,
        text: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Queue a response that emits tool_use blocks (stop_reason='tool_use')."""
        self._queue.append(
            _QueuedResponse(
                content=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_uses=list(tool_uses),
                stop_reason="tool_use",
            )
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "FakeLLMProvider queue is empty — call .queue() or .queue_tool_use() first"
            )
        q = self._queue.pop(0)
        return LLMResponse(
            model=request.model,
            content=q.content,
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            stop_reason=q.stop_reason,
            tool_uses=list(q.tool_uses),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "FakeLLMProvider queue is empty — call .queue() or .queue_tool_use() first"
            )
        q = self._queue.pop(0)
        for ch in q.content:
            yield LLMStreamChunk(delta=ch)
        for tu in q.tool_uses:
            yield LLMStreamChunk(tool_use_start=ToolUseStart(id=tu.id, name=tu.name))
            yield LLMStreamChunk(tool_use_input_delta=json.dumps(tu.input))
            yield LLMStreamChunk(tool_use_stop_id=tu.id)
        yield LLMStreamChunk(
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            done=True,
        )
