"""Typed request/response/stream models shared across all providers.

Tool-use support is additive: `LLMMessage.content` may be a plain `str` (the
Plan 02 shape) or a list of typed `ContentBlock`s (for tool_use turns).
`LLMResponse.content` stays a plain `str` — when the model emits tool_use blocks,
`content` is `""`, `stop_reason == "tool_use"`, and `tool_uses` carries the calls.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ToolDef(BaseModel):
    """Tool definition passed to the model (name, description, JSON schema)."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ToolUse(BaseModel):
    """A single tool_use call emitted by the model in a non-streaming response."""

    id: str
    name: str
    input: dict[str, Any]


class ToolUseStart(BaseModel):
    """Stream event marking the start of a tool_use content block."""

    id: str
    name: str


class TextBlock(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    kind: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    kind: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="kind"),
]


class LLMMessage(BaseModel):
    role: Role
    # `str` preserves the Plan 02 shape exactly. The list variant is only used
    # for tool_use turns; existing callers that pass plain strings are unaffected.
    content: str | list[ContentBlock]


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
    tools: list[ToolDef] = Field(default_factory=list)


class LLMResponse(BaseModel):
    model: str
    # Stays a plain string for backward compatibility with Plan 02 callers.
    content: str
    usage: TokenUsage
    stop_reason: str | None = None
    tool_uses: list[ToolUse] = Field(default_factory=list)


class LLMStreamChunk(BaseModel):
    delta: str = ""
    usage: TokenUsage | None = None
    done: bool = False
    # Tool-use stream events. The session loop accumulates `tool_use_input_delta`
    # chunks between a `tool_use_start` and the next `tool_use_start` or `done`.
    tool_use_start: ToolUseStart | None = None
    tool_use_input_delta: str | None = None
    tool_use_stop_id: str | None = None
