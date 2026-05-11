"""Smoke test for brain_core.tools.undo_last — ToolResult shape.

Covers the ``nothing_to_undo`` branch (missing ``.brain/undo/`` directory) —
which fires before any UndoLog call. brain_mcp's existing test_tool_undo_last.py
covers the happy ``reverted`` path end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.undo_last import NAME, _find_latest_undo_id, handle
from brain_core.vault.types import NewFile, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


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


def _mk_ctx_with_undo(vault: Path) -> ToolContext:
    """Context wired with a real UndoLog — for tests that exercise the
    ``reverted`` branch (which needs ``ctx.undo_log.revert`` to run).
    """
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
        undo_log=UndoLog(vault_root=vault),
    )


def test_name() -> None:
    assert NAME == "brain_undo_last"


def test_find_latest_undo_id_empty(tmp_path: Path) -> None:
    """Missing `.brain/undo/` returns None cleanly."""
    assert _find_latest_undo_id(tmp_path) is None


def test_find_latest_undo_id_picks_lex_last(tmp_path: Path) -> None:
    undo_dir = tmp_path / ".brain" / "undo"
    undo_dir.mkdir(parents=True)
    (undo_dir / "20260101T000000000000.txt").write_text("a", encoding="utf-8")
    (undo_dir / "20260102T000000000000.txt").write_text("b", encoding="utf-8")
    assert _find_latest_undo_id(tmp_path) == "20260102T000000000000"


async def test_nothing_to_undo_when_no_history(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "nothing_to_undo"


async def test_data_keys_pin_nothing_to_undo(tmp_path: Path) -> None:
    """Plan 18 T3.7 drift pin: nothing_to_undo branch emits exactly
    these keys (must match the TS ``UndoLastData`` discriminated union
    at ``apps/brain_web/src/lib/api/tools.ts``).
    """
    result = await handle({}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert set(result.data.keys()) == {"status"}
    assert result.data["status"] == "nothing_to_undo"


async def test_data_keys_pin_reverted(tmp_path: Path) -> None:
    """Plan 18 T3.7 drift pin: reverted branch emits exactly these
    keys (must match the TS ``UndoLastData`` discriminated union).

    Seeds an undo record via VaultWriter.apply, then invokes the tool
    without an explicit ``undo_id`` so the lex-last scan fires.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "research").mkdir()

    writer = VaultWriter(vault_root=vault)
    patchset = PatchSet(
        new_files=[NewFile(path=vault / "research" / "pin.md", content="# pin\n")],
        reason="seed for pin test",
    )
    writer.apply(patchset, allowed_domains=("research",))
    assert (vault / "research" / "pin.md").exists()

    result = await handle({}, _mk_ctx_with_undo(vault))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "undo_id"}
    assert result.data["status"] == "reverted"
    assert isinstance(result.data["undo_id"], str)
    # Revert actually rolled the file back.
    assert not (vault / "research" / "pin.md").exists()
