"""Smoke test for the brain_ping_llm MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.llm.fake import FakeLLMProvider
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.ping_llm import NAME, handle


def test_name() -> None:
    assert NAME == "brain_ping_llm"


async def test_shim_returns_ok_with_fake_provider(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # make_ctx already wires a FakeLLMProvider; queue a probe response.
    assert isinstance(ctx.llm, FakeLLMProvider)
    ctx.llm.queue("ok")
    out = await handle({}, ctx)
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["ok"] is True
    assert data["provider"] == "fake"
