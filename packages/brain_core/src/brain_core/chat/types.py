"""Typed surface for the chat subsystem. Every other chat.* module imports from here."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatMode(StrEnum):
    ASK = "ask"
    BRAINSTORM = "brainstorm"
    DRAFT = "draft"


class TurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"  # mode switches, scope changes, errors surfaced to the transcript


class ChatEventKind(StrEnum):
    DELTA = "delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TURN_END = "turn_end"
    COST_UPDATE = "cost_update"
    PATCH_PROPOSED = "patch_proposed"
    ERROR = "error"


class ChatTurn(BaseModel):
    role: TurnRole
    content: str
    created_at: datetime
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0

    @field_validator("cost_usd")
    @classmethod
    def _non_negative_cost(cls, v: float) -> float:
        if v < 0:
            raise ValueError("cost_usd must be non-negative")
        return v


class ChatEvent(BaseModel):
    """Streamed event from ChatSession. Consumers (CLI, API WS) map 1:1 to their wire format."""

    kind: ChatEventKind
    data: dict[str, Any] = Field(default_factory=dict)


class ChatSessionConfig(BaseModel):
    mode: ChatMode
    domains: tuple[str, ...]
    open_doc_path: Path | None = None
    context_cap_tokens: int = 150_000
    model: str = "claude-sonnet-4-6"

    @field_validator("domains")
    @classmethod
    def _at_least_one_domain(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("at least one domain required")
        return v
