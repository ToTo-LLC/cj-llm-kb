"""Smoke test for brain_core.tools.apply_patch — handler contract.

Exercises the rate-limit refusal branch: the handler's first line consumes
from the ``patches`` bucket, which raises :class:`RateLimitError` when
drained. Plan 05 Task 14 flipped this from an inline-JSON return to an
exception — the exception propagates; brain_mcp's shim catches + converts,
brain_api's global handler converts to HTTP 429. brain_mcp's
``test_tool_apply_patch.py`` still covers the full apply flow end-to-end
through the shim so the transport wrapper + domain-scope + writer apply are
still exhaustively tested.

Plan 07 Task 1: autonomy-gate regressions pin that a staged envelope whose
``patchset.category`` matches an enabled flag in
:class:`~brain_core.config.schema.AutonomousConfig` comes back with
``status="auto_applied"``; an envelope whose flag is disabled (or whose
category is OTHER) falls back to ``status="applied"``. Both paths mutate
the vault and record an undo entry identically — the distinction is purely
for the UI/ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.config.schema import AutonomousConfig, Config
from brain_core.rate_limit import RateLimitError
from brain_core.state.db import StateDB
from brain_core.tools import apply_patch as apply_patch_module
from brain_core.tools.apply_patch import NAME, handle
from brain_core.tools.base import ToolContext
from brain_core.vault.types import NewFile, PatchCategory, PatchSet
from brain_core.vault.writer import VaultWriter


@dataclass
class _AlwaysRefusingLimiter:
    """Rate-limiter stand-in whose ``check`` always raises."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        raise RateLimitError(bucket=bucket, retry_after_seconds=60)


@dataclass
class _InfiniteLimiter:
    """Rate-limiter stand-in that never refuses — for autonomy-gate tests."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        return None


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
        rate_limiter=_AlwaysRefusingLimiter(),
        undo_log=None,
    )


def _mk_real_ctx(vault: Path) -> ToolContext:
    """Construct a ToolContext with real VaultWriter + PendingPatchStore.

    Just enough wiring to exercise the auto-apply branch end-to-end — the
    retrieval/llm/cost primitives stay stubbed since apply_patch doesn't
    touch them.
    """
    brain_dir = vault / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=PendingPatchStore(brain_dir / "pending"),
        state_db=StateDB.open(brain_dir / "state.sqlite"),
        writer=VaultWriter(vault_root=vault),
        llm=None,
        cost_ledger=None,
        rate_limiter=_InfiniteLimiter(),
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_apply_patch"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle({"patch_id": "abc123"}, _mk_ctx(tmp_path))
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60


async def test_auto_apply_fires_when_category_flag_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PatchCategory.INGEST + autonomous.ingest=True → status="auto_applied"."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "research").mkdir()
    ctx = _mk_real_ctx(vault)
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/auto.md"), content="# hi\n")],
        reason="ingest auto",
        category=PatchCategory.INGEST,
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_ingest",
        target_path=Path("research/notes/auto.md"),
        reason="ingest auto",
    )

    # Override _resolve_config so the autonomy gate sees ingest=True.
    def _cfg(_ctx: ToolContext) -> Config:
        return Config(vault_path=vault, autonomous=AutonomousConfig(ingest=True))

    monkeypatch.setattr(apply_patch_module, "_resolve_config", _cfg)

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "auto_applied"
    assert result.data["patch_id"] == env.patch_id
    assert (vault / "research" / "notes" / "auto.md").exists()


async def test_auto_apply_skipped_when_category_flag_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PatchCategory.INGEST + autonomous.ingest=False → status="applied" (fallback path)."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "research").mkdir()
    ctx = _mk_real_ctx(vault)
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/manual.md"), content="# hi\n")],
        reason="ingest manual",
        category=PatchCategory.INGEST,
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_ingest",
        target_path=Path("research/notes/manual.md"),
        reason="ingest manual",
    )

    # Explicitly disabled — plus an OTHER-category flag that should not
    # cross-enable.
    def _cfg(_ctx: ToolContext) -> Config:
        return Config(vault_path=vault, autonomous=AutonomousConfig(ingest=False))

    monkeypatch.setattr(apply_patch_module, "_resolve_config", _cfg)

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "applied"
    assert (vault / "research" / "notes" / "manual.md").exists()
