"""Smoke test for brain_core.tools.ingest — ToolResult shape.

The happy path drives the full IngestPipeline (three LLM calls). For the smoke
test we exercise the rate-limit-refused branch: the handler's first line checks
``ctx.rate_limiter.check("patches", cost=1)`` and returns a refusal ToolResult
without touching the pipeline or the LLM. That verifies the ToolResult contract
without duplicating brain_mcp's end-to-end ingest test coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.ingest import NAME, handle


@dataclass
class _AlwaysRefusingLimiter:
    """Minimal rate-limiter stand-in: every ``check`` refuses."""

    def check(self, bucket: str, *, cost: int = 1) -> bool:
        return False


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


async def test_rate_limit_refusal_short_circuits(tmp_path: Path) -> None:
    result = await handle({"source": "some text"}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "rate_limited"
    assert result.data["bucket"] == "patches"
