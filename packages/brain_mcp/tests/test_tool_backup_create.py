"""Smoke test for the brain_backup_create MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_mcp.tools.backup_create import NAME, handle
from brain_core.tools.base import ToolContext


def test_name() -> None:
    assert NAME == "brain_backup_create"


async def test_shim_creates_tarball(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"trigger": "manual"}, ctx)
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["status"] == "created"
    assert Path(data["path"]).exists()
    assert data["trigger"] == "manual"
