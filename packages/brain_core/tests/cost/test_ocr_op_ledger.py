"""Plan 24 Task 3 / D6 — pin that ``operation="ocr"`` rows round-trip
through :class:`CostLedger` correctly.

The ledger's ``operation`` column is a free-form ``TEXT`` field
(verified in ``cost/ledger.py``), so the only thing this file pins is:

* (a) An ``operation="ocr"`` row writes without error.
* (b) The row is queryable by domain via
      :meth:`CostLedger.domain_spend_within_window` (so the
      :class:`PerDomainBudgetGuard` correctly counts OCR spend against
      the per-domain budget).
* (c) The row contributes to per-domain totals + day totals.
* (d) :class:`OCRResult` is recorded with the correct shape via the
      :func:`brain_core.ingest.ocr.ocr_image` helper end-to-end (uses a
      :class:`FakeLLMProvider`).
* (e) :func:`ocr_image` raises :class:`BudgetCapExceeded` when the
      per-domain cap is exhausted BEFORE the LLM call (cost rail).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from brain_core.budget import BudgetCapExceeded, PerDomainBudgetGuard
from brain_core.config.schema import BudgetOverride, Config
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.ingest.ocr import OCR_OPERATION, ocr_image
from brain_core.llm.fake import FakeLLMProvider


# ---------------------------------------------------------------------------
# (a) op="ocr" row writes
# ---------------------------------------------------------------------------


def test_ocr_op_row_writes_and_reads_back(tmp_path: Path) -> None:
    """Smallest pin: ``operation="ocr"`` is accepted by the ledger schema."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    ts = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)

    ledger.record(
        CostEntry(
            timestamp=ts,
            operation=OCR_OPERATION,
            model="claude-sonnet-4-6",
            input_tokens=400,
            output_tokens=80,
            cost_usd=0.0024,
            domain="work",
        )
    )

    assert round(ledger.total_for_day(ts.date()), 4) == 0.0024


# ---------------------------------------------------------------------------
# (b) PerDomainBudgetGuard counts op="ocr" against per-domain spend
# ---------------------------------------------------------------------------


def test_ocr_op_counts_in_domain_spend_window(tmp_path: Path) -> None:
    """``domain_spend_within_window`` sums op="ocr" rows alongside other ops."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime.now(tz=UTC)

    # Two rows in the same domain, mixed operations.
    ledger.record(
        CostEntry(
            timestamp=now - timedelta(hours=1),
            operation="ingest",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.005,
            domain="research",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=now - timedelta(minutes=30),
            operation=OCR_OPERATION,
            model="claude-sonnet-4-6",
            input_tokens=600,
            output_tokens=40,
            cost_usd=0.003,
            domain="research",
        )
    )

    total = ledger.domain_spend_within_window(
        "research", since=now - timedelta(days=1)
    )
    assert round(total, 4) == 0.008


def test_ocr_op_groups_into_by_domain_totals(tmp_path: Path) -> None:
    """``total_by_domain`` aggregates op="ocr" into the domain bucket."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    ts = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)

    ledger.record(
        CostEntry(
            timestamp=ts,
            operation=OCR_OPERATION,
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=120,
            cost_usd=0.0048,
            domain="work",
        )
    )

    by_domain = ledger.total_by_domain(ts.date())
    assert round(by_domain["work"], 4) == 0.0048


# ---------------------------------------------------------------------------
# (d) ocr_image helper end-to-end with FakeLLMProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ocr_image_records_ledger_row_via_helper(tmp_path: Path) -> None:
    """End-to-end: ``ocr_image`` records a ledger row with op="ocr"
    + correct model + token counts + domain."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)

    llm = FakeLLMProvider()
    llm.queue_vision("found this text", input_tokens=120, output_tokens=15)

    result = await ocr_image(
        image_bytes=b"\x89PNG\r\n\x1a\nfake",
        content_type="image/png",
        domain="work",
        llm_provider=llm,
        cost_ledger=ledger,
        budget_guard=guard,
        config=config,
    )

    assert result.text == "found this text"
    assert result.input_tokens == 120
    assert result.output_tokens == 15
    # Sonnet 4.6 pricing: input 3.0/Mtok, output 15.0/Mtok.
    # 120 * 3 / 1M + 15 * 15 / 1M = 0.00036 + 0.000225 = 0.000585
    assert round(result.cost_usd, 6) == 0.000585
    assert result.model == "claude-sonnet-4-6"

    today = datetime.now(tz=UTC).date()
    by_domain = ledger.total_by_domain(today)
    assert round(by_domain["work"], 6) == 0.000585


@pytest.mark.asyncio
async def test_ocr_image_uses_default_prompt(tmp_path: Path) -> None:
    """Default prompt is "Extract any text visible in this image. ..."."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)

    llm = FakeLLMProvider()
    llm.queue_vision("ok")

    await ocr_image(
        image_bytes=b"x",
        content_type="image/png",
        domain="work",
        llm_provider=llm,
        cost_ledger=ledger,
        budget_guard=guard,
        config=config,
    )

    assert llm.vision_calls[0].prompt.startswith("Extract any text visible")


@pytest.mark.asyncio
async def test_ocr_image_passes_content_type_through(tmp_path: Path) -> None:
    """``content_type`` propagates to ``LLMProvider.vision_extract``."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)

    llm = FakeLLMProvider()
    llm.queue_vision("ok")

    await ocr_image(
        image_bytes=b"x",
        content_type="image/jpeg",
        domain="work",
        llm_provider=llm,
        cost_ledger=ledger,
        budget_guard=guard,
        config=config,
    )

    assert llm.vision_calls[0].content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_ocr_image_explicit_model_override(tmp_path: Path) -> None:
    """Caller-supplied ``model="claude-opus-4-6"`` flows through + recorded in ledger."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)

    llm = FakeLLMProvider()
    llm.queue_vision("ok", input_tokens=100, output_tokens=10)

    result = await ocr_image(
        image_bytes=b"x",
        content_type="image/png",
        domain="work",
        llm_provider=llm,
        cost_ledger=ledger,
        budget_guard=guard,
        config=config,
        model="claude-opus-4-6",
    )

    assert result.model == "claude-opus-4-6"
    assert llm.vision_calls[0].model == "claude-opus-4-6"


@pytest.mark.asyncio
async def test_ocr_image_unknown_model_degrades_cost_to_zero(tmp_path: Path) -> None:
    """Unknown model -> cost_usd=0.0 (graceful degradation; test stubs use fake models)."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)

    llm = FakeLLMProvider()
    llm.queue_vision("ok", input_tokens=100, output_tokens=10)

    result = await ocr_image(
        image_bytes=b"x",
        content_type="image/png",
        domain="work",
        llm_provider=llm,
        cost_ledger=ledger,
        budget_guard=guard,
        config=config,
        model="claude-imaginary-9000",
    )

    assert result.cost_usd == 0.0


# ---------------------------------------------------------------------------
# (e) Budget rail gates OCR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ocr_image_raises_when_per_domain_budget_exhausted(tmp_path: Path) -> None:
    """``ocr_image`` raises :class:`BudgetCapExceeded` BEFORE calling the LLM
    when the per-domain budget is exhausted."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    guard = PerDomainBudgetGuard(ledger)
    config = Config(vault_path=tmp_path)
    # Pin a tight cap on 'work': $0.001 daily.
    config.budget.per_domain = {"work": BudgetOverride(daily_cap_usd=0.001)}

    # Seed a row at-cap so the next call exceeds it.
    ledger.record(
        CostEntry(
            timestamp=datetime.now(tz=UTC) - timedelta(hours=1),
            operation="ingest",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=10,
            cost_usd=0.002,  # 2x the cap
            domain="work",
        )
    )

    llm = FakeLLMProvider()
    # Don't queue a vision response — if the guard fails to fire, this would
    # raise the FakeLLMProvider's "queue is empty" error instead of
    # BudgetCapExceeded. Different error => budget rail didn't gate.

    with pytest.raises(BudgetCapExceeded, match="window=daily"):
        await ocr_image(
            image_bytes=b"x",
            content_type="image/png",
            domain="work",
            llm_provider=llm,
            cost_ledger=ledger,
            budget_guard=guard,
            config=config,
        )

    # Confirm no row was recorded for the gated call.
    assert ledger.domain_spend_within_window(
        "work", since=datetime.now(tz=UTC) - timedelta(days=1)
    ) == 0.002  # only the seeded row, not the OCR row
    # And confirm the LLM was NEVER called (vision queue would have errored if it had been).
    assert llm.vision_calls == []
