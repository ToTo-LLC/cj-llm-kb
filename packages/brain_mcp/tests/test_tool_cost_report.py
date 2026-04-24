"""Tests for the brain_cost_report MCP tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from brain_core.cost.ledger import CostEntry
from brain_core.tools.base import ToolContext
from brain_mcp.tools.cost_report import NAME, handle


def test_name() -> None:
    assert NAME == "brain_cost_report"


async def test_cost_report_with_entries(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    ctx.cost_ledger.record(
        CostEntry(
            timestamp=datetime.now(UTC),
            operation="summarize",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.04,
            domain="research",
        )
    )
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["today_usd"] >= 0.04
    assert data["month_usd"] >= 0.04
    assert "research" in data["by_domain"]


async def test_cost_report_empty_ledger(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["today_usd"] == 0.0
    assert data["month_usd"] == 0.0
    assert data["by_domain"] == {}


async def test_cost_report_text_content_is_human_readable(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    # out[0] is the human-readable text, out[1] is the JSON blob.
    assert "today:" in out[0].text
    assert "month:" in out[0].text
