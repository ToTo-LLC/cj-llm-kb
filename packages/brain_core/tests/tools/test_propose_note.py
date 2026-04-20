"""Smoke test for brain_core.tools.propose_note — handler contract.

Covers the rate-limit refusal path (fires before scope_guard / pending_store)
so we don't need to wire a real PendingPatchStore for this smoke test.
brain_mcp's existing test_tool_propose_note.py still exercises the full
staging flow through the transport shim.

Plan 05 Task 14: ``check()`` raises :class:`RateLimitError` instead of
returning ``False``. The exception propagates out of the handler; brain_mcp
shims catch + convert, brain_api's global handler returns HTTP 429.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.rate_limit import RateLimitError
from brain_core.tools.base import ToolContext
from brain_core.tools.propose_note import NAME, handle


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
    assert NAME == "brain_propose_note"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle(
            {"path": "research/notes/x.md", "content": "hi", "reason": "why"},
            _mk_ctx(tmp_path),
        )
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60
