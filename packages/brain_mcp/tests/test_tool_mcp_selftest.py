"""Smoke test for the brain_mcp_selftest MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.tools.base import ToolContext
from brain_mcp.tools.mcp_selftest import NAME, handle


def test_name() -> None:
    assert NAME == "brain_mcp_selftest"


async def test_shim_fails_cleanly_without_config(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext], tmp_path: Path
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    cfg = tmp_path / "absent.json"
    out = await handle({"config_path": str(cfg)}, ctx)
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["ok"] is False
    assert data["status"] == "failed"
