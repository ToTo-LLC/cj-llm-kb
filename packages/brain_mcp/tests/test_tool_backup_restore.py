"""Smoke test for the brain_backup_restore MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.backup import create_snapshot
from brain_mcp.tools.backup_restore import NAME, handle
from brain_mcp.tools.base import ToolContext


def test_name() -> None:
    assert NAME == "brain_backup_restore"


async def test_shim_requires_typed_confirm(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    meta = create_snapshot(seeded_vault, trigger="manual")
    with pytest.raises(PermissionError):
        await handle(
            {"backup_id": meta.backup_id, "typed_confirm": False},
            ctx,
        )


async def test_shim_restores_with_typed_confirm(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    meta = create_snapshot(seeded_vault, trigger="manual")
    out = await handle(
        {"backup_id": meta.backup_id, "typed_confirm": True},
        ctx,
    )
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["status"] == "restored"
    assert Path(data["trash_path"]).exists()
