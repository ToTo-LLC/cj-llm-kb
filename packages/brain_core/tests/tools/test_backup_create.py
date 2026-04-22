"""Tests for brain_core.tools.backup_create."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest
from brain_core.tools.backup_create import NAME, handle
from brain_core.tools.base import ToolContext, ToolResult


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
    assert NAME == "brain_backup_create"


def _seed_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "research").mkdir()
    (vault / "research" / "note.md").write_text("---\ntitle: Note\n---\nhello\n", encoding="utf-8")
    secrets_dir = vault / ".brain"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "secrets.env").write_text("ANTHROPIC_API_KEY=sk-xxx\n", encoding="utf-8")
    run_dir = secrets_dir / "run"
    run_dir.mkdir()
    (run_dir / "pid").write_text("1234", encoding="utf-8")


async def test_creates_tarball_in_backups_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)

    result = await handle({"trigger": "manual"}, _mk_ctx(vault))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "created"
    assert result.data["trigger"] == "manual"
    tarball = Path(result.data["path"])
    assert tarball.exists()
    assert tarball.parent == vault / ".brain" / "backups"


async def test_backup_excludes_secrets_and_run(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)

    result = await handle({"trigger": "manual"}, _mk_ctx(vault))
    assert result.data is not None
    tarball = Path(result.data["path"])
    with tarfile.open(tarball, "r:gz") as tar:
        names = tar.getnames()
    # Every entry is rooted under "vault/" by arcname.
    assert any(n.endswith("research/note.md") for n in names)
    # Hard rails: secrets.env and run/ are excluded.
    assert not any(n.endswith("secrets.env") for n in names)
    assert not any("/.brain/run/" in n or n.endswith("/run/pid") for n in names)


async def test_rejects_invalid_trigger(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    with pytest.raises(ValueError, match="trigger"):
        await handle({"trigger": "bogus"}, _mk_ctx(vault))


async def test_default_trigger_is_manual(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    result = await handle({}, _mk_ctx(vault))
    assert result.data is not None
    assert result.data["trigger"] == "manual"
