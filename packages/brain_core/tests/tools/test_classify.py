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
    """Rate-limiter stand-in: every ``check`` succeeds (no raise, no return)."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        return None


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


async def test_classify_uses_config_classify_model_when_set(tmp_path: Path) -> None:
    """Issue #31: when ToolContext.config is wired, the classify tool routes
    through ``config.llm.classify_model`` instead of the hardcoded fallback.
    """
    from dataclasses import replace

    from brain_core.config.schema import LLMConfig

    class _Cfg:
        llm = LLMConfig(classify_model="claude-haiku-OVERRIDE")

    llm = FakeLLMProvider()
    llm.queue(
        json.dumps({"source_type": "text", "domain": "research", "confidence": 0.9})
    )
    ctx = replace(_mk_ctx(tmp_path, llm), config=_Cfg())

    await handle({"content": "test"}, ctx)

    # FakeLLMProvider records every request; assert the model used matches the
    # config override.
    assert len(llm.requests) == 1
    assert llm.requests[0].model == "claude-haiku-OVERRIDE"


async def test_classify_falls_back_when_config_is_none(tmp_path: Path) -> None:
    """Issue #31: when ctx.config is None (the default), the classify tool
    falls back to the hardcoded model — matches pre-fix behavior so existing
    ToolContext construction sites stay source-compatible.
    """
    from brain_core.tools.classify import _CLASSIFY_MODEL_FALLBACK

    llm = FakeLLMProvider()
    llm.queue(
        json.dumps({"source_type": "text", "domain": "research", "confidence": 0.9})
    )
    ctx = _mk_ctx(tmp_path, llm)
    assert ctx.config is None  # sanity

    await handle({"content": "test"}, ctx)

    assert len(llm.requests) == 1
    assert llm.requests[0].model == _CLASSIFY_MODEL_FALLBACK
