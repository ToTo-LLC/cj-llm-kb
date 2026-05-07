"""Plan 16 Task 28 — :class:`PerDomainBudgetGuard` pin tests.

Six required cases lock the guard's contract per the plan:

* (a) no override for ``ctx.domain`` -> no-op
* (b) only daily set, under cap -> no-op
* (c) daily exceeded -> raises with ``window=daily`` in the message
* (d) only monthly set, under cap -> no-op
* (e) monthly exceeded -> raises with ``window=monthly`` in the message
* (f) both set, only one exceeded -> raises with the correct window

Plus three architectural-invariant pins:

* (g) both caps ``None`` -> no-op (skip ledger query)
* (h) :class:`BudgetCapExceeded` is a :class:`RuntimeError` subclass
* (i) ``ctx.domain is None`` -> no-op (legacy threading still works)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from brain_core.budget import BudgetCapExceeded, PerDomainBudgetGuard
from brain_core.config.schema import BudgetOverride, Config
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.tools.base import ToolContext


def _make_ctx(
    *,
    vault_path: Path,
    domain: str | None,
    per_domain: dict[str, BudgetOverride],
) -> ToolContext:
    """Build a :class:`ToolContext` minimally populated for the guard.

    The guard reads ``ctx.domain`` and ``ctx.config.budget.per_domain``
    only — every other ToolContext field stays at its dummy default.
    """
    config = Config(vault_path=vault_path)
    config.budget.per_domain = per_domain
    return ToolContext(
        vault_root=vault_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=config,
        domain=domain,
    )


def _seed(ledger: CostLedger, *, domain: str, cost_usd: float, hours_ago: float) -> None:
    """Record a single ledger entry at ``now - hours_ago`` for ``domain``."""
    ts = datetime.now(tz=UTC) - timedelta(hours=hours_ago)
    ledger.record(
        CostEntry(
            timestamp=ts,
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=100,
            cost_usd=cost_usd,
            domain=domain,
        )
    )


# ---------------------------------------------------------------------------
# (a) no override -> no-op
# ---------------------------------------------------------------------------


def test_no_override_for_domain_is_noop(tmp_path: Path) -> None:
    """Empty ``per_domain`` dict means no enforcement."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=999.0, hours_ago=1)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(vault_path=tmp_path, domain="research", per_domain={})

    guard.check(ctx)  # no override -> no-op even with $999 spent


# ---------------------------------------------------------------------------
# (b) only daily set, under cap -> no-op
# ---------------------------------------------------------------------------


def test_daily_only_under_cap_is_noop(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=0.50, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={"research": BudgetOverride(daily_cap_usd=1.00)},
    )

    guard.check(ctx)


# ---------------------------------------------------------------------------
# (c) daily exceeded -> raises with window=daily
# ---------------------------------------------------------------------------


def test_daily_exceeded_raises_with_daily_window(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=1.50, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={"research": BudgetOverride(daily_cap_usd=1.00)},
    )

    with pytest.raises(BudgetCapExceeded) as exc:
        guard.check(ctx)

    msg = str(exc.value)
    assert "domain=research" in msg
    assert "window=daily" in msg
    assert "cap=1.0" in msg


# ---------------------------------------------------------------------------
# (d) only monthly set, under cap -> no-op
# ---------------------------------------------------------------------------


def test_monthly_only_under_cap_is_noop(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=5.00, hours_ago=24 * 5)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={"research": BudgetOverride(monthly_cap_usd=20.00)},
    )

    guard.check(ctx)


# ---------------------------------------------------------------------------
# (e) monthly exceeded -> raises with window=monthly
# ---------------------------------------------------------------------------


def test_monthly_exceeded_raises_with_monthly_window(tmp_path: Path) -> None:
    """Spread spend across the 30-day window so it sums above the cap.

    Each entry stays under the (non-existent) daily cap at $3, but the
    sum across the 30-day window ($21) exceeds the $20 monthly cap.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    for hours_ago in (24 * 1, 24 * 5, 24 * 10, 24 * 15, 24 * 20, 24 * 25, 24 * 28):
        _seed(ledger, domain="research", cost_usd=3.00, hours_ago=hours_ago)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={"research": BudgetOverride(monthly_cap_usd=20.00)},
    )

    with pytest.raises(BudgetCapExceeded) as exc:
        guard.check(ctx)

    msg = str(exc.value)
    assert "domain=research" in msg
    assert "window=monthly" in msg
    assert "cap=20.0" in msg


# ---------------------------------------------------------------------------
# (f) both set, only one exceeded -> raises with correct window
# ---------------------------------------------------------------------------


def test_both_caps_only_monthly_exceeded_reports_monthly_window(tmp_path: Path) -> None:
    """Daily under cap, monthly over cap -> message must say monthly.

    Entries are placed > 24h ago so the daily window sums to $0; the
    full 30-day window sums to $21 which exceeds the $20 monthly cap.
    Daily cap is $5 (well above $0).
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    for hours_ago in (48, 72, 96, 120, 144, 168, 192):
        _seed(ledger, domain="research", cost_usd=3.00, hours_ago=hours_ago)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={
            "research": BudgetOverride(daily_cap_usd=5.00, monthly_cap_usd=20.00),
        },
    )

    with pytest.raises(BudgetCapExceeded) as exc:
        guard.check(ctx)

    msg = str(exc.value)
    assert "window=monthly" in msg
    assert "window=daily" not in msg


def test_both_caps_only_daily_exceeded_reports_daily_window(tmp_path: Path) -> None:
    """Daily over cap, monthly under cap -> message must say daily.

    Single recent entry of $3 exceeds the $1 daily cap; monthly cap is
    $20 which the same $3 sits well under.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=3.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={
            "research": BudgetOverride(daily_cap_usd=1.00, monthly_cap_usd=20.00),
        },
    )

    with pytest.raises(BudgetCapExceeded) as exc:
        guard.check(ctx)

    msg = str(exc.value)
    assert "window=daily" in msg
    assert "window=monthly" not in msg


# ---------------------------------------------------------------------------
# (g) both caps None -> no-op (architectural invariant: skip ledger query)
# ---------------------------------------------------------------------------


def test_both_caps_none_is_noop(tmp_path: Path) -> None:
    """``BudgetOverride()`` with both caps ``None`` is a no-op even with spend.

    Locks the architectural invariant: the guard skips the ledger query
    entirely when there's nothing to enforce.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=999.0, hours_ago=1)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain="research",
        per_domain={"research": BudgetOverride()},
    )

    guard.check(ctx)


# ---------------------------------------------------------------------------
# (h) BudgetCapExceeded is a RuntimeError
# ---------------------------------------------------------------------------


def test_budget_cap_exceeded_is_runtime_error() -> None:
    """Locks the exception hierarchy: callers that catch ``RuntimeError``
    keep working; callers that catch the legacy ``BudgetExceededError``
    do NOT catch this one (different class, same parent)."""
    assert issubclass(BudgetCapExceeded, RuntimeError)


# ---------------------------------------------------------------------------
# (i) ctx.domain is None -> no-op
# ---------------------------------------------------------------------------


def test_ctx_domain_none_is_noop(tmp_path: Path) -> None:
    """A call site that hasn't threaded ``ctx.domain`` falls through cleanly.

    The legacy global :class:`BudgetEnforcer` remains the only safety net
    in that path; this guard is opt-in via threading.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed(ledger, domain="research", cost_usd=999.0, hours_ago=1)
    guard = PerDomainBudgetGuard(ledger)
    ctx = _make_ctx(
        vault_path=tmp_path,
        domain=None,
        per_domain={"research": BudgetOverride(daily_cap_usd=1.00)},
    )

    guard.check(ctx)
