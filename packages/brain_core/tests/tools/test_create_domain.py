"""Smoke test for brain_core.tools.create_domain — slug rules + atomic create."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.create_domain import NAME, handle


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_create_domain"


async def test_creates_domain_folder_and_seed_files(tmp_path: Path) -> None:
    result = await handle({"slug": "music", "name": "Music"}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "created"
    assert result.data["domain"]["slug"] == "music"

    domain_dir = tmp_path / "music"
    assert domain_dir.is_dir()
    index_path = domain_dir / "index.md"
    log_path = domain_dir / "log.md"
    assert index_path.exists()
    assert log_path.exists()
    body = index_path.read_text(encoding="utf-8")
    assert "# Music" in body
    assert "domain" not in body or "type: index" in body  # frontmatter present


async def test_invalid_slug_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must match"):
        await handle({"slug": "Bad-Slug", "name": "Bad"}, _mk_ctx(tmp_path))
    # Folder must not exist after a rejected call.
    assert not (tmp_path / "Bad-Slug").exists()


async def test_existing_slug_rejected(tmp_path: Path) -> None:
    (tmp_path / "music").mkdir()
    with pytest.raises(FileExistsError):
        await handle({"slug": "music", "name": "Music"}, _mk_ctx(tmp_path))


async def test_appends_slug_to_config_domains_in_memory(tmp_path: Path) -> None:
    """Plan 10 Task 5: a successful create appends the slug to
    ``ctx.config.domains`` in-memory so subsequent classify / list_domains
    calls see the new slug without a restart. Disk persistence is
    deferred to issue #27.
    """
    from brain_core.config.schema import Config

    cfg = Config(domains=["research", "work", "personal"])
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research", "work", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )
    result = await handle({"slug": "hobby", "name": "Hobby"}, ctx)

    assert result.data is not None
    assert result.data["status"] == "created"
    assert "hobby" in cfg.domains  # in-memory append landed
    assert (tmp_path / "hobby" / "index.md").exists()


async def test_rejects_slug_already_in_config_domains(tmp_path: Path) -> None:
    """Plan 10 Task 5: refusing a slug already configured prevents the
    state-divergence case where Config has it but no folder yet.
    """
    from brain_core.config.schema import Config

    cfg = Config(domains=["research", "work", "personal", "hobby"])
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research", "work", "personal", "hobby"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )
    # No folder for "hobby" on disk, but it IS in Config.domains.
    with pytest.raises(FileExistsError, match=r"Config\.domains"):
        await handle({"slug": "hobby", "name": "Hobby"}, ctx)
    assert not (tmp_path / "hobby").exists()
