"""Rendering + contract tests for the chat_ask mode prompt.

Rendering tests load the plain-text mode prompt via `brain_core.chat.modes.MODES`
and assert structural properties. No network.

Contract tests are skipped placeholders until cassettes are recorded against
the real Anthropic API (Plan 03 D7a deferral).
"""

from __future__ import annotations

import pytest
from brain_core.chat.modes import MODES
from brain_core.chat.types import ChatMode


class TestChatAskRendering:
    """No-network rendering tests for the chat_ask mode prompt."""

    def test_prompt_loads(self) -> None:
        text = MODES[ChatMode.ASK].prompt_text
        assert len(text) > 200

    def test_ask_prompt_mentions_citations(self) -> None:
        text = MODES[ChatMode.ASK].prompt_text.lower()
        assert "cite" in text or "citation" in text or "[[" in text

    def test_ask_prompt_forbids_speculation(self) -> None:
        text = MODES[ChatMode.ASK].prompt_text.lower()
        assert "speculat" in text or "don't know" in text or "refuse" in text


# ---------------------------------------------------------------------------
# Contract test skeleton — deferred until cassettes are recorded.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="chat_ask cassette not yet recorded (Plan 03 D7a deferral)",
)
@pytest.mark.asyncio
async def test_chat_ask_real_api_returns_cited_answer() -> None:
    """Placeholder for the real-API contract test.

    Will assert: given a simple "what is the LLM wiki pattern?" query plus
    a mock vault with a karpathy.md note, the response cites [[karpathy]]
    and does not hallucinate unrelated claims. Records a VCR cassette when
    `ANTHROPIC_API_KEY` is set and `RUN_LIVE_LLM_TESTS=1`.
    """
    raise NotImplementedError("chat_ask contract test not yet recorded")
