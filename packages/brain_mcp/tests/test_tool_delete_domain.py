"""Smoke test for the brain_delete_domain MCP shim."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext
from brain_mcp.tools.delete_domain import NAME, handle


def test_name() -> None:
    assert NAME == "brain_delete_domain"


async def test_shim_refuses_personal(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(PermissionError, match="personal"):
        await handle({"slug": "personal", "typed_confirm": True}, ctx)


async def test_shim_moves_domain_and_returns_undo_id(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # Seed an extra domain that's safe to nuke (personal is protected;
    # research/work are used by other test helpers).
    (seeded_vault / "music").mkdir()
    (seeded_vault / "music" / "index.md").write_text(
        "---\ntitle: music\n---\n# music\n", encoding="utf-8"
    )

    out = await handle({"slug": "music", "typed_confirm": True}, ctx)
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert data["status"] == "deleted"
    assert "undo_id" in data
    assert not (seeded_vault / "music").exists()
