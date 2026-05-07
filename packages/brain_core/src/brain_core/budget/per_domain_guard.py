"""Per-domain budget enforcement (Plan 16 Task 28 / D26 step 3 of 4).

Composition over inheritance: this guard does NOT extend the legacy
:class:`brain_core.cost.budget.BudgetEnforcer`. Call sites that need both
checks call them in sequence — the legacy global cap first, then this
per-domain cap. This keeps the two guards independently testable and
avoids a deep class hierarchy that would couple their lifecycles.

Window semantics (locked by the plan):

* Daily window  = ``now - 24h`` (rolling, not calendar day).
* Monthly window = ``now - 30d`` (rolling, not calendar month).

A future iteration can add calendar-aligned windows behind a config
flag, but the rolling shape matches the spec wording ("daily AND monthly
windows") and the existing :func:`CostLedger.domain_spend_within_window`
contract that locks ``ts_utc >= since``.

The "≥ cap" comparison is intentional: the cap is the upper limit, so a
spent total equal to the cap is treated as exhausted (next call would
push us over). This matches the spec footnote on D26 step 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from brain_core.cost.ledger import CostLedger
    from brain_core.tools.base import ToolContext


@dataclass(frozen=True, slots=True)
class _GuardCtxShim:
    """Minimal duck-typed ctx for :meth:`PerDomainBudgetGuard.check`.

    Plan 16 Task 28.5: LLM entry points outside the tool layer (chat
    session, ingest pipeline, autotitle, fork) don't carry a full
    :class:`brain_core.tools.base.ToolContext` — they only know the
    per-call domain and the active :class:`Config`. ``check()`` reads
    just ``domain`` and ``config`` via :func:`getattr`, so a 2-field
    shim satisfies its contract without forcing call sites to build a
    fully-populated ToolContext.
    """

    domain: str | None
    config: Any  # Config | None — typed Any to avoid an import cycle


class BudgetCapExceeded(RuntimeError):  # noqa: N818  # name locked by Plan 16 Task 28 spec / D26 step 3 of 4
    """Raised when a per-domain budget cap would be exceeded.

    Inherits ``RuntimeError`` per Plan 16 Task 28 architectural invariant:
    the legacy :class:`brain_core.cost.budget.BudgetExceededError` does the
    same, so call sites that already catch ``RuntimeError`` (or its
    ``BudgetExceededError`` subclass) keep working when this new class
    layers in.

    Message shape: ``"domain={...}, window={daily|monthly}, spent={...}, cap={...}"``.
    The structured shape matters because the Settings UI parses it to
    surface "research domain hit its monthly cap" without re-querying the
    ledger.
    """


class PerDomainBudgetGuard:
    """Per-domain pre-call budget guard.

    Invoked before every LLM call by the call site (chat.py, ingest
    pipeline). Reads ``ctx.config.budget.per_domain[ctx.domain]``; if no
    override exists or both caps are ``None``, returns immediately
    without querying the ledger (avoids the SQL trip on the hot path).

    Threading note: ``ctx.domain`` is an optional ``str | None`` field on
    :class:`brain_core.tools.base.ToolContext`. When ``None`` (e.g. a
    legacy call site that hasn't been threaded yet, or a tool that has
    no single per-call domain), the guard no-ops — the global guard
    remains the safety net.
    """

    def __init__(self, ledger: CostLedger) -> None:
        self._ledger = ledger

    def check(self, ctx: ToolContext) -> None:
        """Raise :class:`BudgetCapExceeded` if ``ctx.domain``'s daily or monthly cap is exhausted.

        No-op when:

        * ``ctx.domain`` is ``None`` (call site hasn't threaded a domain).
        * ``ctx.config`` is ``None`` (low-level harness without a config).
        * No override exists for ``ctx.domain``.
        * The override exists but both caps are ``None``.

        Otherwise queries the cost ledger for the relevant rolling window
        and raises with a structured message when ``spent >= cap`` for
        either window. Daily is checked first, so a domain that has
        breached both gets the daily message — call sites that want both
        surfaced should re-invoke after lifting the daily cap.
        """
        domain = getattr(ctx, "domain", None)
        if domain is None:
            return

        cfg = getattr(ctx, "config", None)
        if cfg is None:
            return

        override = cfg.budget.per_domain.get(domain)
        if override is None:
            return
        if override.daily_cap_usd is None and override.monthly_cap_usd is None:
            return

        now = datetime.now(tz=UTC)

        if override.daily_cap_usd is not None:
            since = now - timedelta(days=1)
            spent = self._ledger.domain_spend_within_window(domain, since=since)
            if spent >= override.daily_cap_usd:
                raise BudgetCapExceeded(
                    f"domain={domain}, window=daily, "
                    f"spent={spent:.4f}, cap={override.daily_cap_usd}"
                )

        if override.monthly_cap_usd is not None:
            since = now - timedelta(days=30)
            spent = self._ledger.domain_spend_within_window(domain, since=since)
            if spent >= override.monthly_cap_usd:
                raise BudgetCapExceeded(
                    f"domain={domain}, window=monthly, "
                    f"spent={spent:.4f}, cap={override.monthly_cap_usd}"
                )

    def check_for(self, *, domain: str | None, config: Any) -> None:
        """Convenience wrapper: build a :class:`_GuardCtxShim` and call :meth:`check`.

        Plan 16 Task 28.5 entry-point wiring uses this for call sites that
        don't carry a full :class:`brain_core.tools.base.ToolContext` (chat
        session, ingest pipeline, autotitle, fork). Behavior is identical
        to :meth:`check` — same no-op rules, same exception, same message
        shape — so the pin tests in
        ``tests/budget/test_per_domain_guard.py`` cover both surfaces.
        """
        # ``check`` is typed against the full ``ToolContext`` (the public
        # tool-layer entry shape), but its body reads only ``domain`` and
        # ``config`` via :func:`getattr`. The ``_GuardCtxShim`` satisfies
        # that read contract — the cast is a structural-typing concession,
        # not a soundness violation; the runtime behavior is identical.
        self.check(cast("ToolContext", _GuardCtxShim(domain=domain, config=config)))
