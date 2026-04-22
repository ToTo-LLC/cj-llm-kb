"""Tests for brain_core.tools.ping_llm."""

from __future__ import annotations

from pathlib import Path

from brain_core.llm.fake import FakeLLMProvider
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.ping_llm import NAME, handle


def _mk_ctx(vault: Path, *, llm: object | None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=llm,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_ping_llm"


async def test_happy_path_returns_latency_and_provider(tmp_path: Path) -> None:
    llm = FakeLLMProvider()
    llm.queue("ok", input_tokens=1, output_tokens=1)
    result = await handle({}, _mk_ctx(tmp_path, llm=llm))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["ok"] is True
    assert result.data["provider"] == "fake"
    assert isinstance(result.data["latency_ms"], int)
    assert result.data["latency_ms"] >= 0


async def test_provider_failure_returns_ok_false(tmp_path: Path) -> None:
    class _BoomLLM:
        name = "boom"

        async def complete(self, request: object) -> object:
            raise RuntimeError("provider exploded")

        def stream(self, request: object) -> object:
            raise NotImplementedError

    result = await handle({}, _mk_ctx(tmp_path, llm=_BoomLLM()))
    assert result.data is not None
    assert result.data["ok"] is False
    assert "provider exploded" in result.data["error"]
    assert result.data["provider"] == "boom"


async def test_missing_provider_does_not_raise(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path, llm=None))
    assert result.data is not None
    assert result.data["ok"] is False
    assert "no llm provider" in result.data["error"].lower()


async def test_model_override_passes_through(tmp_path: Path) -> None:
    llm = FakeLLMProvider()
    llm.queue("ok")
    result = await handle({"model": "claude-opus-test"}, _mk_ctx(tmp_path, llm=llm))
    assert result.data is not None
    assert result.data["ok"] is True
    assert llm.requests[0].model == "claude-opus-test"
