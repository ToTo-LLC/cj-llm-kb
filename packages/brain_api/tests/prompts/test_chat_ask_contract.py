"""Real-API contract test for Ask-mode chat turn. Deferred per Plan 05 D9a.

When cassettes exist, removes the skipif and runs against recorded responses.
To record:
    ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest \\
        -k chat_ask_contract packages/brain_api/tests/prompts -v
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 05 D9a deferral — chat Ask-mode cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_chat_ask_real_api_produces_citation_bearing_delta_stream() -> None:
    """Placeholder for real-API contract test.

    Will assert: given a seeded vault and an Ask-mode prompt that requires
    search, the WS stream emits in order: tool_call(brain_search) →
    tool_result → delta chunks → cost_update → turn_end. Assistant text
    cites at least one wikilink from the vault.
    """
    raise NotImplementedError("chat Ask-mode contract test not yet recorded")
