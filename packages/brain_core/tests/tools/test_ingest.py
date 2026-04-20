"""Smoke test for brain_core.tools.ingest — handler contract.

The happy path drives the full IngestPipeline (three LLM calls). For the
smoke test we exercise the rate-limit-refused branch: the handler's first
line calls ``ctx.rate_limiter.check("patches", cost=1)``, which raises
:class:`RateLimitError` when the bucket is drained. Plan 05 Task 14 flipped
this from an inline-JSON return to an exception — the exception propagates;
brain_mcp's shim catches + converts, brain_api's global handler converts to
HTTP 429. brain_mcp's end-to-end ingest test still covers the happy path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.rate_limit import RateLimitError
from brain_core.tools.base import ToolContext
from brain_core.tools.ingest import NAME, handle


@dataclass
class _AlwaysRefusingLimiter:
    """Rate-limiter stand-in whose ``check`` always raises."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        raise RateLimitError(bucket=bucket, retry_after_seconds=60)


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=_AlwaysRefusingLimiter(),
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_ingest"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle({"source": "some text"}, _mk_ctx(tmp_path))
    # ingest checks the patches bucket first — that's the one that fires.
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60
