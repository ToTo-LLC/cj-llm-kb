"""Smoke test for brain_core.tools.apply_patch — handler contract.

Exercises the rate-limit refusal branch: the handler's first line consumes
from the ``patches`` bucket, which raises :class:`RateLimitError` when
drained. Plan 05 Task 14 flipped this from an inline-JSON return to an
exception — the exception propagates; brain_mcp's shim catches + converts,
brain_api's global handler converts to HTTP 429. brain_mcp's
``test_tool_apply_patch.py`` still covers the full apply flow end-to-end
through the shim so the transport wrapper + domain-scope + writer apply are
still exhaustively tested.

Plan 07 Task 1 / Plan 16 Task 39: autonomy-gate regressions pin that a
staged envelope whose populated member fields and category are fully
covered by flags in
``Config.autonomous[domain]: AutonomyCategoryFlags`` for the patch's
target domain comes back with ``status="auto_applied"``; an envelope
whose required flags are missing (or whose category is OTHER) falls
back to ``status="applied"``. Both paths mutate the vault and record
an undo entry identically — the distinction is purely for the UI/ledger.

Plan 16 Task 39.5: ``_resolve_config`` now returns ``ctx.config`` when set
(production path: brain_api / brain_mcp / brain_cli thread Config in via
T34.5+ wiring). When ``ctx.config is None`` (low-level harness contexts) it
falls back to the original ``Config(vault_path=ctx.vault_root)`` stub. The
two ``_resolve_config_*`` unit tests + the end-to-end ``ctx.config``
auto-apply / staging tests below pin this branch split.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.config.schema import AutonomyCategoryFlags, Config
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


def _mk_real_ctx(vault: Path, *, config: Config | None = None) -> ToolContext:
    """Construct a ToolContext with real VaultWriter + PendingPatchStore.

    Just enough wiring to exercise the auto-apply branch end-to-end — the
    retrieval/llm/cost primitives stay stubbed since apply_patch doesn't
    touch them. ``config`` defaults to ``None`` so the legacy stub-fallback
    path (preserved by Plan 16 Task 39.5) is exercised by tests that
    monkeypatch ``_resolve_config``. Tests that want the production-shape
    "ctx.config drives the gate" branch pass an explicit ``Config(...)``.
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
        config=config,
    )


def test_name() -> None:
    assert NAME == "brain_apply_patch"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle({"patch_id": "abc123"}, _mk_ctx(tmp_path))
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60


async def test_auto_apply_fires_when_member_field_flag_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INGEST patch + ``research`` flags include ``new_files=True`` →
    ``status="auto_applied"``. Plan 16 Task 39 HYBRID: INGEST has no
    category-level flag requirement, so member-field coverage alone
    drives auto-apply."""
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

    # Override _resolve_config so the autonomy gate sees the per-domain
    # entry. Under HYBRID, an INGEST patch with new_files populated needs
    # ``flags.new_files=True`` for the target domain (here ``research``).
    def _cfg(_ctx: ToolContext) -> Config:
        return Config(
            vault_path=vault,
            autonomous={"research": AutonomyCategoryFlags(new_files=True)},
        )

    monkeypatch.setattr(apply_patch_module, "_resolve_config", _cfg)

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "auto_applied"
    assert result.data["patch_id"] == env.patch_id
    assert (vault / "research" / "notes" / "auto.md").exists()


async def test_auto_apply_skipped_when_member_field_flag_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INGEST patch + per-domain flags with ``new_files=False`` →
    ``status="applied"`` (fallback path through the standard apply).
    Plan 16 Task 39 HYBRID intersection: any False flag on a populated
    member field stages the whole patch."""
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

    # Per-domain entry exists but the required member-field flag is
    # explicitly False — the gate stages the patch. Other flags being
    # True must NOT cross-enable.
    def _cfg(_ctx: ToolContext) -> Config:
        return Config(
            vault_path=vault,
            autonomous={
                "research": AutonomyCategoryFlags(
                    new_files=False,
                    edits=True,
                    index_entries=True,
                    concepts=True,
                    draft=True,
                )
            },
        )

    monkeypatch.setattr(apply_patch_module, "_resolve_config", _cfg)

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "applied"
    assert (vault / "research" / "notes" / "manual.md").exists()


# ---------------------------------------------------------------------------
# Plan 16 Task 39.5 — _resolve_config branch split + production-wiring
# end-to-end pin tests. The function returns ``ctx.config`` when set
# (production path through brain_api / brain_mcp / brain_cli lifespans);
# otherwise it falls back to ``Config(vault_path=ctx.vault_root)`` so
# low-level harness contexts that don't supply a Config keep the original
# safe-defaults stub behavior.
# ---------------------------------------------------------------------------


def test_resolve_config_falls_back_to_defaults_when_ctx_config_none(tmp_path: Path) -> None:
    """``_resolve_config(ctx)`` with ``ctx.config is None`` returns the stub.

    Pre-T39.5 behavior — preserved for low-level harness contexts. The
    returned Config has ``vault_path`` overlaid from ``ctx.vault_root`` and
    schema defaults for everything else (notably ``autonomous == {}``, so
    the gate is OFF for every domain when no Config is wired).
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    ctx = _mk_real_ctx(vault, config=None)
    cfg = apply_patch_module._resolve_config(ctx)
    assert cfg.vault_path == vault
    assert cfg.autonomous == {}


def test_resolve_config_returns_ctx_config_by_identity(tmp_path: Path) -> None:
    """``_resolve_config(ctx)`` with ``ctx.config`` set returns it BY IDENTITY.

    The autonomy gate must read the user's actual ``Config.autonomous`` map
    — an upstream defensive ``model_copy`` would silently break the
    "production lifespan threaded the live Config through" wiring.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg_in = Config(
        vault_path=vault,
        autonomous={"research": AutonomyCategoryFlags(new_files=True)},
    )
    ctx = _mk_real_ctx(vault, config=cfg_in)
    cfg_out = apply_patch_module._resolve_config(ctx)
    # ``is`` not ``==`` is load-bearing: production wiring relies on the
    # exact same reference flowing through so in-place edits made in other
    # layers (e.g. config_set / brain_web → save_config) are visible to
    # subsequent gate evaluations within the same process.
    assert cfg_out is cfg_in


async def test_apply_patch_auto_applies_when_ctx_config_drives_gate(
    tmp_path: Path,
) -> None:
    """End-to-end: ``ctx.config`` populated with the right per-domain flags
    auto-applies WITHOUT a monkeypatch on ``_resolve_config``.

    Pin test for the wiring half of T39.5. Pre-T39.5, even production callers
    that threaded Config onto ToolContext would fall through to the stub's
    empty-autonomous defaults — patches never auto-applied. Post-T39.5, the
    handler reads ``ctx.config`` directly.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "research").mkdir()
    cfg = Config(
        vault_path=vault,
        autonomous={"research": AutonomyCategoryFlags(new_files=True)},
    )
    ctx = _mk_real_ctx(vault, config=cfg)
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/wired.md"), content="# hi\n")],
        reason="ingest wired",
        category=PatchCategory.INGEST,
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_ingest",
        target_path=Path("research/notes/wired.md"),
        reason="ingest wired",
    )

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "auto_applied"
    assert (vault / "research" / "notes" / "wired.md").exists()


async def test_apply_patch_stages_when_ctx_config_disables_gate(
    tmp_path: Path,
) -> None:
    """End-to-end: ``ctx.config`` with the required member-field flag
    explicitly ``False`` routes the patch to the standard apply (i.e.
    ``status="applied"``, NOT ``auto_applied``). Mirrors the
    monkeypatch-driven cousin above but proves the production-shape wiring.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "research").mkdir()
    cfg = Config(
        vault_path=vault,
        autonomous={
            "research": AutonomyCategoryFlags(
                new_files=False,
                edits=True,
                index_entries=True,
                concepts=True,
                draft=True,
            )
        },
    )
    ctx = _mk_real_ctx(vault, config=cfg)
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/staged.md"), content="# hi\n")],
        reason="ingest staged",
        category=PatchCategory.INGEST,
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_ingest",
        target_path=Path("research/notes/staged.md"),
        reason="ingest staged",
    )

    result = await handle({"patch_id": env.patch_id}, ctx)
    assert result.data is not None
    assert result.data["status"] == "applied"
    assert (vault / "research" / "notes" / "staged.md").exists()
