"""Smoke test for brain_core.tools.apply_patch — handler contract.

Exercises the rate-limit refusal branch: the handler's first line consumes
from the ``patches`` bucket, which raises :class:`RateLimitError` when
drained. Plan 05 Task 14 flipped this from an inline-JSON return to an
exception — the exception propagates; brain_mcp's shim catches + converts,
brain_api's global handler converts to HTTP 429. brain_mcp's
``test_tool_apply_patch.py`` still covers the full apply flow end-to-end
through the shim so the transport wrapper + domain-scope + writer apply are
still exhaustively tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.rate_limit import RateLimitError
from brain_core.tools.apply_patch import NAME, handle
from brain_core.tools.base import ToolContext


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
    assert NAME == "brain_apply_patch"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle({"patch_id": "abc123"}, _mk_ctx(tmp_path))
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60
