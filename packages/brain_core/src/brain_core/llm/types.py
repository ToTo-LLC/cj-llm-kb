"""Typed request/response/stream models shared across all providers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class LLMMessage(BaseModel):
    role: Role
    content: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    stop_sequences: list[str] = Field(default_factory=list)


class LLMResponse(BaseModel):
    model: str
    content: str
    usage: TokenUsage
    stop_reason: str | None = None


class LLMStreamChunk(BaseModel):
    delta: str = ""
    usage: TokenUsage | None = None
    done: bool = False
