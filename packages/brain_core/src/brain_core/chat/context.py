"""ContextCompiler — build the prompt context for a single chat turn.

Layers (in order):
    1. BRAIN.md (if present)
    2. mode-specific system prompt (passed in at construction)
    3. <domain>/index.md for every in-scope domain
    4. Explicitly-read notes from prior turns (via read_note tool)

Token estimation is len(text)//4 — close enough for a local tool.
Hard cap trims oldest messages, never the system or final user message.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.chat.types import ChatSessionConfig, ChatTurn, TurnRole


def _est_tokens(text: str) -> int:
    return len(text) // 4


@dataclass(frozen=True)
class CompiledContext:
    system: str
    messages: list[dict[str, Any]]
    estimated_tokens: int


class ContextCompiler:
    def __init__(self, vault_root: Path, mode_prompt: str) -> None:
        self.vault_root = vault_root
        self.mode_prompt = mode_prompt

    def compile(
        self,
        config: ChatSessionConfig,
        turns: list[ChatTurn],
        read_notes: dict[Path, str],
        user_message: str,
    ) -> CompiledContext:
        """Build a CompiledContext for one chat turn."""
        system_parts: list[str] = []

        brain_md = self.vault_root / "BRAIN.md"
        if brain_md.exists():
            system_parts.append(brain_md.read_text(encoding="utf-8"))

        system_parts.append(self.mode_prompt)

        for domain in config.domains:
            idx = self.vault_root / domain / "index.md"
            if idx.exists():
                system_parts.append(f"# index: {domain}\n\n{idx.read_text(encoding='utf-8')}")

        for path, body in read_notes.items():
            system_parts.append(f"# note: {path.as_posix()}\n\n{body}")

        system = "\n\n".join(system_parts)

        messages: list[dict[str, Any]] = [self._turn_to_message(t) for t in turns]
        messages.append({"role": "user", "content": user_message})

        cap = config.context_cap_tokens
        total = _est_tokens(system) + sum(_est_tokens(m["content"]) for m in messages)
        # Trim oldest messages (front of list) until under cap. Never remove the
        # final user message — always leave at least one message in the list.
        while total > cap and len(messages) > 1:
            dropped = messages.pop(0)
            total -= _est_tokens(dropped["content"])

        return CompiledContext(system=system, messages=messages, estimated_tokens=total)

    def _turn_to_message(self, turn: ChatTurn) -> dict[str, Any]:
        if turn.role == TurnRole.SYSTEM:
            # Anthropic API only has user/assistant/system (top-level). We
            # surface in-transcript system messages (mode switches etc.) as
            # assistant narration tagged [system] so the model sees them.
            return {"role": "assistant", "content": f"[system] {turn.content}"}
        return {"role": turn.role.value, "content": turn.content}
