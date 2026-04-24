"""Smoke test for the brain_backup_list MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.backup import create_snapshot
from brain_mcp.tools.backup_list import NAME, handle
from brain_core.tools.base import ToolContext


def test_name() -> None:
    assert NAME == "brain_backup_list"


async def test_shim_lists_existing_snapshots(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    create_snapshot(seeded_vault, trigger="manual")
    out = await handle({}, ctx)
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert len(data["backups"]) == 1
    assert data["backups"][0]["trigger"] == "manual"
