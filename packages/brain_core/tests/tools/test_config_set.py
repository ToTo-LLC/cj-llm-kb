"""Smoke test for brain_core.tools.config_set — ToolResult shape + refusals.

Covers: secret-like refusal, non-settable-key refusal, and a successful
in-memory "updated" write on an allowlisted key. brain_mcp's existing
test_tool_config_get_set.py covers the transport wrapper behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_set import _SETTABLE_KEYS, NAME, handle


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
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_config_set"


def test_settable_keys_match_plan_07_task_4() -> None:
    """Allowlist is deliberately narrow; active_domain is NOT settable.

    Plan 04 baseline: ``budget.daily_usd`` + ``log_llm_payloads``.
    Plan 07 Task 1: adds the 5 ``autonomous.<category>`` flags.
    Plan 07 Task 2: adds the 3 per-mode ``{mode}_model`` overrides.
    Plan 07 Task 4: adds ``domain_order`` + 2 ``budget.override_*`` fields.
    """
    assert (
        frozenset(
            {
                "budget.daily_usd",
                "log_llm_payloads",
                "autonomous.ingest",
                "autonomous.entities",
                "autonomous.concepts",
                "autonomous.index_rewrites",
                "autonomous.draft",
                "ask_model",
                "brainstorm_model",
                "draft_model",
                "domain_order",
                "budget.override_until",
                "budget.override_delta_usd",
            }
        )
        == _SETTABLE_KEYS
    )


async def test_allows_autonomous_flag(tmp_path: Path) -> None:
    """Each new autonomy key accepts a bool without secret-refusal or allowlist-refusal."""
    for key in (
        "autonomous.ingest",
        "autonomous.entities",
        "autonomous.concepts",
        "autonomous.index_rewrites",
        "autonomous.draft",
    ):
        result = await handle({"key": key, "value": True}, _mk_ctx(tmp_path))
        assert isinstance(result, ToolResult)
        assert result.data is not None
        assert result.data["status"] == "updated"
        assert result.data["value"] is True


async def test_refuses_secret_like_key(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="secret-like"):
        await handle({"key": "llm.api_key", "value": "nope"}, _mk_ctx(tmp_path))


async def test_refuses_non_allowlisted_key(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="not settable"):
        await handle({"key": "active_domain", "value": "research"}, _mk_ctx(tmp_path))


async def test_allows_budget_daily_usd(tmp_path: Path) -> None:
    result = await handle(
        {"key": "budget.daily_usd", "value": 5.0},
        _mk_ctx(tmp_path),
    )

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is False
    assert result.data["value"] == 5.0
