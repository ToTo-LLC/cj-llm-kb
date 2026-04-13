"""FakeLLMProvider — queue-based stub for tests. No network calls ever."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage


@dataclass
class _QueuedResponse:
    content: str
    input_tokens: int
    output_tokens: int


class FakeLLMProvider:
    name = "fake"

    def __init__(self) -> None:
        self._queue: list[_QueuedResponse] = []
        self.requests: list[LLMRequest] = []

    def queue(self, content: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._queue.append(
            _QueuedResponse(content=content, input_tokens=input_tokens, output_tokens=output_tokens)
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "FakeLLMProvider queue is empty — call .queue() before .complete()"
            )
        q = self._queue.pop(0)
        return LLMResponse(
            model=request.model,
            content=q.content,
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            stop_reason="end_turn",
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "FakeLLMProvider queue is empty — call .queue() before .stream()"
            )
        q = self._queue.pop(0)
        for ch in q.content:
            yield LLMStreamChunk(delta=ch)
        yield LLMStreamChunk(
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            done=True,
        )
