"""Real-API contract test for Brainstorm-mode chat turn. Deferred per Plan 05 D9a.

When cassettes exist, removes the skipif and runs against recorded responses.
To record:
    ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest \\
        -k chat_brainstorm_contract packages/brain_api/tests/prompts -v
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 05 D9a deferral — chat Brainstorm-mode cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_chat_brainstorm_real_api_emits_patch_proposed_event() -> None:
    """Placeholder for real-API contract test.

    Will assert: given a Brainstorm-mode prompt that encourages the model
    to reshape an existing note, the WS stream emits a `patch_proposed`
    event sourced from a `propose_note` tool call. Event payload carries a
    valid PatchSet id that resolves via the pending-store approval queue.
    """
    raise NotImplementedError("chat Brainstorm-mode contract test not yet recorded")
