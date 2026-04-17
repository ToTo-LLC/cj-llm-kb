"""Real-API contract test for brain_ingest. Deferred per Plan 04 D9a.

When cassettes exist, removes the skipif and runs against the recorded
responses. To record: ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest
-k brain_ingest_contract.
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 04 D9a deferral — brain_ingest cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_brain_ingest_real_api_produces_valid_patchset() -> None:
    """Placeholder for real-API contract test.

    Will assert: given a URL source and a mock vault, the ingest pipeline
    produces a PatchSet with at least one new_file, the classify step returns
    `research` with confidence > 0.7, and the total cost is recorded in the
    ledger.
    """
    raise NotImplementedError("brain_ingest contract test not yet recorded")
