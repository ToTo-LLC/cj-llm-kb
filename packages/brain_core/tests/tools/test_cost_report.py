"""Smoke test for brain_core.tools.cost_report — ToolResult shape.

Drives the handler through a stub ``CostLedger`` that returns a fixed
``CostSummary``. This pins the output envelope (today_usd / month_usd /
by_domain) without needing the ledger's sqlite backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from brain_core.cost.ledger import CostSummary
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.cost_report import NAME, handle


@dataclass
class _StubLedger:
    """CostLedger stand-in: returns a fixed CostSummary."""

    summary_value: CostSummary

    def summary(self, *, today: date, month: tuple[int, int]) -> CostSummary:
        _ = today, month
        return self.summary_value


def _mk_ctx(vault: Path, ledger: _StubLedger) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=ledger,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_cost_report"


async def test_returns_fixed_summary(tmp_path: Path) -> None:
    ledger = _StubLedger(
        summary_value=CostSummary(
            today_usd=0.1234,
            month_usd=1.2345,
            by_domain={"research": 0.1234},
        )
    )

    result = await handle({}, _mk_ctx(tmp_path, ledger))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["today_usd"] == 0.1234
    assert result.data["month_usd"] == 1.2345
    assert result.data["by_domain"] == {"research": 0.1234}
    assert "research=$0.1234" in result.text
