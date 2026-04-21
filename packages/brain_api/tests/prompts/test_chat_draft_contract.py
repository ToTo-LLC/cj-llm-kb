"""Real-API contract test for Draft-mode chat turn. Deferred per Plan 05 D9a.

When cassettes exist, removes the skipif and runs against recorded responses.
To record:
    ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest \\
        -k chat_draft_contract packages/brain_api/tests/prompts -v
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 05 D9a deferral — chat Draft-mode cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_chat_draft_real_api_streams_open_doc_edit_deltas() -> None:
    """Placeholder for real-API contract test.

    Will assert: given a Draft-mode turn with an open document attached as
    background context, the model invokes `edit_open_doc` and the WS stream
    surfaces the resulting diff as `delta` events addressed to the open doc
    (not the thread transcript). Cost ledger entry carries mode=draft.
    """
    raise NotImplementedError("chat Draft-mode contract test not yet recorded")
