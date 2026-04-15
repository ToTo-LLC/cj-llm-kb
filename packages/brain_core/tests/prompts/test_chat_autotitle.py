"""Rendering + contract tests for the chat_autotitle prompt.

Unlike the three chat mode prompts, chat_autotitle is a structured-output
prompt with YAML frontmatter and a registered schema. It is loaded via
`load_prompt("chat_autotitle")`.

Contract tests are skipped placeholders until cassettes are recorded against
the real Anthropic API (Plan 03 D7a deferral).
"""

from __future__ import annotations

import pytest
from brain_core.prompts.loader import load_prompt


class TestChatAutotitleRendering:
    """No-network rendering tests for the chat_autotitle prompt."""

    def test_prompt_loads(self) -> None:
        prompt = load_prompt("chat_autotitle")
        assert prompt.name == "chat_autotitle"
        assert len(prompt.system) > 100
        assert "{turns}" in prompt.user_template

    def test_autotitle_prompt_mentions_json_schema(self) -> None:
        prompt = load_prompt("chat_autotitle")
        system = prompt.system
        assert "JSON" in system or '"title"' in system or '"slug"' in system

    def test_autotitle_prompt_mentions_constraints(self) -> None:
        prompt = load_prompt("chat_autotitle")
        system = prompt.system
        assert "3" in system
        assert "6" in system or "word" in system.lower()


# ---------------------------------------------------------------------------
# Contract test skeleton — deferred until cassettes are recorded.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="chat_autotitle cassette not yet recorded (Plan 03 D7a deferral)",
)
@pytest.mark.asyncio
async def test_chat_autotitle_real_api_returns_valid_schema() -> None:
    """Placeholder for the real-API contract test.

    Will assert: given two mock chat turns, the assistant returns a JSON
    object matching `ChatAutotitleOutput` with a 3-6 word lowercase title
    and a kebab-case slug. Records a VCR cassette when `ANTHROPIC_API_KEY`
    is set and `RUN_LIVE_LLM_TESTS=1`.
    """
    raise NotImplementedError("chat_autotitle contract test not yet recorded")
