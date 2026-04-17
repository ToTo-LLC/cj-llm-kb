"""Real-API contract test for brain_bulk_import. Deferred per Plan 04 D9a.

When cassettes exist, removes the skipif and runs against the recorded
responses. To record: ANTHROPIC_API_KEY=sk-... RUN_LIVE_LLM_TESTS=1 uv run pytest
-k brain_bulk_import_contract.
"""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    True,
    reason="Plan 04 D9a deferral — brain_bulk_import cassette not yet recorded",
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_brain_bulk_import_real_api_produces_valid_patchset() -> None:
    """Placeholder for real-API contract test.

    Will assert: given a folder of mixed-source files, the bulk import tool
    produces one PatchSet per source with a PatchSet for each file, each
    classify step returns a valid domain, and the total cost across the
    batch is recorded in the ledger.
    """
    raise NotImplementedError("brain_bulk_import contract test not yet recorded")
