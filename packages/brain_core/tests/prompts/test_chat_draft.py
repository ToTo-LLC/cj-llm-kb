"""Rendering + contract tests for the chat_draft mode prompt.

Rendering tests load the plain-text mode prompt via `brain_core.chat.modes.MODES`
and assert structural properties. No network.

Contract tests are skipped placeholders until cassettes are recorded against
the real Anthropic API (Plan 03 D7a deferral).
"""

from __future__ import annotations

import pytest
from brain_core.chat.modes import MODES
from brain_core.chat.types import ChatMode


class TestChatDraftRendering:
    """No-network rendering tests for the chat_draft mode prompt."""

    def test_prompt_loads(self) -> None:
        text = MODES[ChatMode.DRAFT].prompt_text
        assert len(text) > 200

    def test_draft_prompt_mentions_open_document(self) -> None:
        text = MODES[ChatMode.DRAFT].prompt_text.lower()
        assert "open document" in text or "open doc" in text

    def test_draft_prompt_mentions_edit_open_doc(self) -> None:
        text = MODES[ChatMode.DRAFT].prompt_text
        assert "edit_open_doc" in text


# ---------------------------------------------------------------------------
# Contract test skeleton — deferred until cassettes are recorded.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="chat_draft cassette not yet recorded (Plan 03 D7a deferral)",
)
@pytest.mark.asyncio
async def test_chat_draft_real_api_edits_open_doc() -> None:
    """Placeholder for the real-API contract test.

    Will assert: given an open document and a targeted edit request, the
    assistant calls `edit_open_doc` with a precise `old`/`new` pair rather
    than rewriting the whole document. Records a VCR cassette when
    `ANTHROPIC_API_KEY` is set and `RUN_LIVE_LLM_TESTS=1`.
    """
    raise NotImplementedError("chat_draft contract test not yet recorded")
