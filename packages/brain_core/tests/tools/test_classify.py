"""Smoke test for brain_core.tools.classify — ToolResult shape."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from brain_core.llm.fake import FakeLLMProvider
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.classify import NAME, handle


@dataclass
class _AllowAllLimiter:
    """Rate-limiter stand-in: every ``check`` passes."""

    def check(self, bucket: str, *, cost: int = 1) -> bool:
        return True


def _mk_ctx(vault: Path, llm: FakeLLMProvider) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=llm,
        cost_ledger=None,
        rate_limiter=_AllowAllLimiter(),
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_classify"


async def test_classify_research_content(tmp_path: Path) -> None:
    llm = FakeLLMProvider()
    llm.queue(
        json.dumps(
            {
                "source_type": "text",
                "domain": "research",
                "confidence": 0.9,
            }
        )
    )

    result = await handle({"content": "Andrej Karpathy on transformers"}, _mk_ctx(tmp_path, llm))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["domain"] == "research"
    assert result.data["confidence"] == 0.9
    assert result.data["source_type"] == "text"
