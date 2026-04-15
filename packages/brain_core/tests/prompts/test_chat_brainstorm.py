"""Rendering + contract tests for the chat_brainstorm mode prompt.

Rendering tests load the plain-text mode prompt via `brain_core.chat.modes.MODES`
and assert structural properties. No network.

Contract tests are skipped placeholders until cassettes are recorded against
the real Anthropic API (Plan 03 D7a deferral).
"""

from __future__ import annotations

import pytest
from brain_core.chat.modes import MODES
from brain_core.chat.types import ChatMode


class TestChatBrainstormRendering:
    """No-network rendering tests for the chat_brainstorm mode prompt."""

    def test_prompt_loads(self) -> None:
        text = MODES[ChatMode.BRAINSTORM].prompt_text
        assert len(text) > 200

    def test_brainstorm_prompt_mentions_pushback(self) -> None:
        text = MODES[ChatMode.BRAINSTORM].prompt_text.lower()
        assert "push back" in text or "alternative" in text or "socratic" in text

    def test_brainstorm_prompt_mentions_propose_note(self) -> None:
        text = MODES[ChatMode.BRAINSTORM].prompt_text
        assert "propose_note" in text


# ---------------------------------------------------------------------------
# Contract test skeleton — deferred until cassettes are recorded.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="chat_brainstorm cassette not yet recorded (Plan 03 D7a deferral)",
)
@pytest.mark.asyncio
async def test_chat_brainstorm_real_api_pushes_back() -> None:
    """Placeholder for the real-API contract test.

    Will assert: given a user framing with an obvious gap, the assistant
    either pushes back or asks a clarifying question, and does not simply
    agree. Records a VCR cassette when `ANTHROPIC_API_KEY` is set and
    `RUN_LIVE_LLM_TESTS=1`.
    """
    raise NotImplementedError("chat_brainstorm contract test not yet recorded")
