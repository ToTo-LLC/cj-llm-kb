"""LLMProvider Protocol — every concrete provider must satisfy this."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from brain_core.llm.types import LLMRequest, LLMResponse, LLMStreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    """Contract every LLM backend must honor."""

    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]: ...
