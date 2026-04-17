"""Real-API contract test for brain_classify. Deferred per Plan 04 D9a.

When cassettes exist, removes the skipif and runs against the recorded
responses. To record: ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest
-k brain_classify_contract.
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 04 D9a deferral — brain_classify cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_brain_classify_real_api_produces_valid_patchset() -> None:
    """Placeholder for real-API contract test.

    Will assert: given an unknown snippet of text, the classify tool returns
    a `{source_type, domain, confidence}` triple where `domain` is one of
    the allowed domains and `confidence` is in [0, 1]. Cost for the call is
    recorded in the ledger.
    """
    raise NotImplementedError("brain_classify contract test not yet recorded")
