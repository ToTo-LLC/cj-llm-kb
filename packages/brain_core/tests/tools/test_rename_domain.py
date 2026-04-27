"""Smoke test for brain_core.tools.rename_domain — atomic rename + undo round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.rename_domain import NAME, handle
from brain_core.vault.undo import UndoLog


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


def _seed_research(vault: Path) -> None:
    (vault / "research" / "notes").mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "---\ntitle: Research\ndomain: research\ntype: index\n---\n\n# Research\n",
        encoding="utf-8",
    )
    (vault / "research" / "notes" / "alpha.md").write_text(
        "---\ntitle: Alpha\ndomain: research\n---\n\nbody\n",
        encoding="utf-8",
    )


def test_name() -> None:
    assert NAME == "brain_rename_domain"


async def test_renames_folder_and_rewrites_frontmatter(tmp_path: Path) -> None:
    _seed_research(tmp_path)

    result = await handle(
        {"from": "research", "to": "lab-notes"},
        _mk_ctx(tmp_path),
    )

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "renamed"
    assert result.data["from"] == "research"
    assert result.data["to"] == "lab-notes"
    assert result.data["files_updated"] == 2
    assert result.data["undo_id"]

    # Old folder gone, new folder present.
    assert not (tmp_path / "research").exists()
    new_dir = tmp_path / "lab-notes"
    assert new_dir.is_dir()
    new_alpha = (new_dir / "notes" / "alpha.md").read_text(encoding="utf-8")
    assert "domain: lab-notes" in new_alpha
    assert "domain: research" not in new_alpha


async def test_undo_log_round_trip_reverses_rename(tmp_path: Path) -> None:
    _seed_research(tmp_path)

    result = await handle(
        {"from": "research", "to": "lab-notes"},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    undo_id = result.data["undo_id"]

    # Apply the undo.
    UndoLog(vault_root=tmp_path).revert(undo_id)

    # Folder is back; frontmatter restored.
    assert (tmp_path / "research").is_dir()
    assert not (tmp_path / "lab-notes").exists()
    restored = (tmp_path / "research" / "notes" / "alpha.md").read_text(encoding="utf-8")
    assert "domain: research" in restored


async def test_rejects_when_destination_exists(tmp_path: Path) -> None:
    _seed_research(tmp_path)
    (tmp_path / "lab-notes").mkdir()

    with pytest.raises(FileExistsError):
        await handle(
            {"from": "research", "to": "lab-notes"},
            _mk_ctx(tmp_path),
        )
    # Source folder untouched.
    assert (tmp_path / "research").exists()


async def test_rejects_invalid_slug(tmp_path: Path) -> None:
    """Plan 10 Task 5: slug rules unified with Config.domains validation.

    The error message wording shifted from the v0.1 ``"... fails ^[a-z]..."``
    to the schema-level ``"... must match [a-z][a-z0-9_-]..."`` form when
    the tool was migrated to ``_validate_domain_slug``. We assert on the
    stable substring ``"must match"``.
    """
    _seed_research(tmp_path)
    with pytest.raises(ValueError, match="must match"):
        await handle(
            {"from": "research", "to": "Lab-Notes"},
            _mk_ctx(tmp_path),
        )


async def test_rejects_renaming_personal_slug(tmp_path: Path) -> None:
    """Plan 10 D5: ``personal`` is the privacy-railed slug; rename is refused
    in either direction.
    """
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    (tmp_path / "personal" / "index.md").write_text(
        "---\ntitle: Personal\ndomain: personal\n---\n# Personal\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="privacy"):
        await handle(
            {"from": "personal", "to": "private"},
            _mk_ctx(tmp_path),
        )
    # And the inverse — renaming TO ``personal`` is also refused.
    _seed_research(tmp_path)
    with pytest.raises(PermissionError, match="reserved"):
        await handle(
            {"from": "research", "to": "personal"},
            _mk_ctx(tmp_path),
        )
