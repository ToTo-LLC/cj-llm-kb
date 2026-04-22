"""Smoke test for the brain_set_api_key MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.set_api_key import NAME, handle


def test_name() -> None:
    assert NAME == "brain_set_api_key"


async def test_shim_saves_key_and_masks(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle(
        {"provider": "anthropic", "api_key": "sk-ant-xxxxYYYYzzzz1234"},
        ctx,
    )
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["status"] == "saved"
    assert data["env_key"] == "ANTHROPIC_API_KEY"
    assert "1234" in data["masked"]
    assert "YYYY" not in data["masked"]
