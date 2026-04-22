"""Smoke test for the brain_mcp_install MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.mcp_install import NAME, handle


def test_name() -> None:
    assert NAME == "brain_mcp_install"


async def test_shim_returns_text_and_json(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext], tmp_path: Path
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    cfg = tmp_path / "claude_desktop_config.json"
    out = await handle(
        {"command": "/bin/brain-mcp", "config_path": str(cfg)},
        ctx,
    )
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["status"] == "installed"
