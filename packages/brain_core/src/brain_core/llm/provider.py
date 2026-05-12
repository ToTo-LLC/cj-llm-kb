"""LLMProvider Protocol — every concrete provider must satisfy this.

Plan 24 Task 3 / D4: adds :meth:`vision_extract` to the Protocol so OCR
calls flow through the same abstraction as ``complete`` / ``stream``.
Per CLAUDE.md non-negotiable #4 the abstraction lives here, on the
LLMProvider Protocol — call sites (T4 OCR pass) import this Protocol,
NOT a concrete SDK. Swapping vision providers in the future is a
config change, not a refactor.

Return shape ``tuple[str, int, int]`` = (extracted_text, input_tokens,
output_tokens). The caller records cost via :class:`CostLedger` rather
than the provider doing it inline — keeps the provider stateless (no
ledger dep) and lets the call site stamp the row with the right
``domain`` / ``stage`` tags.
"""

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

    async def vision_extract(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        content_type: str = "image/png",
        model: str | None = None,
    ) -> tuple[str, int, int]: ...
