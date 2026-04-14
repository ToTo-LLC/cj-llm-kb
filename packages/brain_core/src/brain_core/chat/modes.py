"""Mode policy table + ChatTool -> ToolDef adapter.

Pure data module. Defines the per-mode (tool_allowlist, temperature, prompt_text)
policy consumed by the Task 17 session loop, and a small helper to convert a
ChatTool into the LLMRequest.tools ToolDef shape.

The three chat mode prompts live beside the Plan 02 prompts in
`brain_core/prompts/`, but unlike those they are plain-text markdown files with
no YAML frontmatter and no registered output schema — chat prompts return
free-form assistant text (optionally with tool_use blocks), not structured JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.chat.tools.base import ChatTool
from brain_core.chat.types import ChatMode
from brain_core.llm.types import ToolDef

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Read-only tools available in every mode.
_READ_TOOLS: tuple[str, ...] = ("search_vault", "read_note", "list_index", "list_chats")


@dataclass(frozen=True)
class ModePolicy:
    """Per-mode configuration: allowed tools, sampling temperature, system prompt."""

    mode: ChatMode
    tool_allowlist: tuple[str, ...]
    temperature: float
    prompt_text: str


def _load_prompt(filename: str) -> str:
    """Load a chat mode prompt as plain text. No frontmatter, no schema."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


MODES: dict[ChatMode, ModePolicy] = {
    ChatMode.ASK: ModePolicy(
        mode=ChatMode.ASK,
        tool_allowlist=_READ_TOOLS,
        temperature=0.2,
        prompt_text=_load_prompt("chat_ask.md"),
    ),
    ChatMode.BRAINSTORM: ModePolicy(
        mode=ChatMode.BRAINSTORM,
        tool_allowlist=(*_READ_TOOLS, "propose_note"),
        temperature=0.8,
        prompt_text=_load_prompt("chat_brainstorm.md"),
    ),
    ChatMode.DRAFT: ModePolicy(
        mode=ChatMode.DRAFT,
        tool_allowlist=(*_READ_TOOLS, "propose_note", "edit_open_doc"),
        temperature=0.4,
        prompt_text=_load_prompt("chat_draft.md"),
    ),
}


def tool_to_tooldef(tool: ChatTool) -> ToolDef:
    """Convert a ChatTool to a ToolDef suitable for LLMRequest.tools."""
    return ToolDef(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
    )
