"""Plan 16 Task 33: ``brain_repair_config`` + ``brain_repair_config_apply`` tool tests.

Pin the per-step results contract documented in the Plan 16 D28 step 1 of 3
spec (mirroring ``brain doctor``'s shape):

  * Each step row carries ``{step, status, message}``.
  * ``status`` is one of ``"success" | "warning" | "error"``.
  * Steps that did NOT run (because earlier steps succeeded) are NOT in
    the rows list.
  * ``repair_changes_pending`` is True iff the repaired Config differs
    from ``ctx.config`` (deep model_dump compare).

The fallback chain mirrors :func:`brain_core.config.loader.load_config`:
primary read → primary validate → backup read (only if primary failed) →
backup validate → defaults fallback (only if both prior pairs failed).

Plan 16 Task 33 / D28 step 1 of 3 — adjudicated Option 1 (two tools, two
responsibilities) per the dispatch text. ``brain_repair_config`` is a
diagnostic read; ``brain_repair_config_apply`` writes the repaired payload
to disk via :func:`brain_core.config.writer.save_config`. The split mirrors
``brain_backup_create`` / ``brain_backup_restore`` and lets the frontend
two-action flow (Re-run / Re-apply) hit independent endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.repair_config import NAME as REPAIR_NAME
from brain_core.tools.repair_config import handle as repair_handle
from brain_core.tools.repair_config_apply import NAME as APPLY_NAME
from brain_core.tools.repair_config_apply import handle as apply_handle


def _mk_ctx(vault: Path, *, config: Config) -> ToolContext:
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
        config=config,
    )


# ---------------------------------------------------------------------------
# brain_repair_config — diagnostic read
# ---------------------------------------------------------------------------


def test_name_repair() -> None:
    assert REPAIR_NAME == "brain_repair_config"


def test_name_apply() -> None:
    assert APPLY_NAME == "brain_repair_config_apply"


async def test_primary_clean_two_steps_no_changes(tmp_path: Path) -> None:
    """Happy path: primary reads + validates cleanly, in-memory matches."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    # Persist the same Config that's in ctx.config so deep-equal returns True.
    in_memory = Config(active_domain="research")
    primary.write_text(
        json.dumps(in_memory.persisted_dict(), default=str), encoding="utf-8"
    )

    result = await repair_handle({}, _mk_ctx(tmp_path, config=in_memory))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    steps = result.data["steps"]
    assert isinstance(steps, list)
    assert len(steps) == 2
    assert steps[0]["step"] == "read_primary"
    assert steps[0]["status"] == "success"
    assert steps[1]["step"] == "validate_primary"
    assert steps[1]["status"] == "success"
    # Backup + defaults steps did NOT run — must not appear.
    assert all(s["step"] not in {"read_backup", "validate_backup", "apply_defaults"} for s in steps)
    # In-memory matches the on-disk repaired Config — no diff to apply.
    assert result.data["repair_changes_pending"] is False
    assert "repaired_config" in result.data
    repaired = result.data["repaired_config"]
    assert isinstance(repaired, dict)
    assert repaired["active_domain"] == "research"


async def test_primary_missing_falls_back_to_bak(tmp_path: Path) -> None:
    """Primary missing → bak read+validate succeed. 3 steps + diff vs in-memory."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    # No primary file. Bak holds a config with a different active_domain.
    bak = brain_dir / "config.json.bak"
    bak_cfg = Config(active_domain="research")
    bak.write_text(json.dumps(bak_cfg.persisted_dict(), default=str), encoding="utf-8")

    # In-memory ctx.config differs (active_domain="work") so the diff fires.
    in_memory = Config(domains=["research", "work", "personal"], active_domain="work")

    result = await repair_handle({}, _mk_ctx(tmp_path, config=in_memory))

    assert result.data is not None
    steps = result.data["steps"]
    assert len(steps) == 3
    # Order: primary read (warning — missing), backup read (success), backup validate (success).
    assert steps[0]["step"] == "read_primary"
    assert steps[0]["status"] == "warning"
    assert steps[1]["step"] == "read_backup"
    assert steps[1]["status"] == "success"
    assert steps[2]["step"] == "validate_backup"
    assert steps[2]["status"] == "success"
    # Repaired (from .bak) differs from in-memory ctx.config.
    assert result.data["repair_changes_pending"] is True
    assert result.data["repaired_config"]["active_domain"] == "research"


async def test_primary_corrupt_falls_back_to_bak(tmp_path: Path) -> None:
    """Primary parses-fail → bak rescue. 3 steps: read_primary error +
    read_backup success + validate_backup success. (No validate_primary,
    because the read step itself failed; no apply_repair row, because the
    successful validate_backup is the recovery signal.)"""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    primary.write_text("{not json", encoding="utf-8")
    bak = brain_dir / "config.json.bak"
    bak_cfg = Config()
    bak.write_text(json.dumps(bak_cfg.persisted_dict(), default=str), encoding="utf-8")

    result = await repair_handle({}, _mk_ctx(tmp_path, config=Config()))

    assert result.data is not None
    steps = result.data["steps"]
    assert len(steps) == 3
    assert steps[0]["step"] == "read_primary"
    assert steps[0]["status"] == "error"
    assert "parse" in steps[0]["message"].lower() or "json" in steps[0]["message"].lower()
    assert steps[1]["step"] == "read_backup"
    assert steps[1]["status"] == "success"
    assert steps[2]["step"] == "validate_backup"
    assert steps[2]["status"] == "success"
    # Repaired matches the in-memory default Config so no apply needed.
    assert result.data["repair_changes_pending"] is False


async def test_primary_and_bak_corrupt_falls_back_to_defaults(tmp_path: Path) -> None:
    """Both files corrupt → defaults fallback. 3 steps (read_primary error,
    read_backup error, apply_defaults success). When the read step fails
    we do NOT also run validate, so the row count is 3, not 5 — matches
    "actually attempted" semantics."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    bak = brain_dir / "config.json.bak"
    primary.write_text("{not json", encoding="utf-8")
    bak.write_text("also not json", encoding="utf-8")

    # Seed an in-memory Config that differs from defaults so the diff lights up.
    in_memory = Config(active_domain="research", web_port=5500)

    result = await repair_handle({}, _mk_ctx(tmp_path, config=in_memory))

    assert result.data is not None
    steps = result.data["steps"]
    assert len(steps) == 3
    assert steps[0]["step"] == "read_primary"
    assert steps[0]["status"] == "error"
    assert steps[1]["step"] == "read_backup"
    assert steps[1]["status"] == "error"
    assert steps[2]["step"] == "apply_defaults"
    assert steps[2]["status"] == "success"
    # Repaired = Config() defaults, which differs from the seeded in_memory.
    assert result.data["repair_changes_pending"] is True
    assert result.data["repaired_config"]["web_port"] == 4317  # default


async def test_primary_invalid_schema_falls_back_to_bak(tmp_path: Path) -> None:
    """Primary parses but Pydantic rejects → bak rescue."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    # Valid JSON but a field with a bad type — Pydantic will reject on construction.
    primary.write_text(json.dumps({"web_port": "not an int"}), encoding="utf-8")
    bak = brain_dir / "config.json.bak"
    bak.write_text(json.dumps(Config().persisted_dict(), default=str), encoding="utf-8")

    result = await repair_handle({}, _mk_ctx(tmp_path, config=Config()))

    assert result.data is not None
    steps = result.data["steps"]
    # Primary read OK, primary validate fail, bak read OK, bak validate OK.
    assert len(steps) == 4
    assert steps[0]["step"] == "read_primary"
    assert steps[0]["status"] == "success"
    assert steps[1]["step"] == "validate_primary"
    assert steps[1]["status"] == "error"
    assert steps[2]["step"] == "read_backup"
    assert steps[2]["status"] == "success"
    assert steps[3]["step"] == "validate_backup"
    assert steps[3]["status"] == "success"


async def test_returns_repaired_config_as_persisted_dict(tmp_path: Path) -> None:
    """``repaired_config`` is the persisted-dict shape (no vault_path leak)."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    cfg = Config(active_domain="research")
    primary.write_text(json.dumps(cfg.persisted_dict(), default=str), encoding="utf-8")

    result = await repair_handle({}, _mk_ctx(tmp_path, config=cfg))

    assert result.data is not None
    repaired = result.data["repaired_config"]
    # ``vault_path`` is NOT in the persisted-dict allowlist; never leak it.
    assert "vault_path" not in repaired
    # ``config_version`` IS persisted (Plan 16 Task 34).
    assert "config_version" in repaired


async def test_text_summary_present(tmp_path: Path) -> None:
    """ToolResult.text is non-empty so the LLM / chat surface gets a summary."""
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir()
    primary = brain_dir / "config.json"
    primary.write_text(json.dumps(Config().persisted_dict(), default=str), encoding="utf-8")

    result = await repair_handle({}, _mk_ctx(tmp_path, config=Config()))

    assert isinstance(result.text, str)
    assert len(result.text) > 0


# ---------------------------------------------------------------------------
# brain_repair_config_apply — write
# ---------------------------------------------------------------------------


async def test_apply_writes_repaired_payload(tmp_path: Path) -> None:
    """Happy path: apply tool writes the payload via save_config."""
    in_memory = Config(active_domain="research")
    target = tmp_path / ".brain" / "config.json"
    assert not target.exists()

    repaired_payload = Config(
        active_domain="research", web_port=5500
    ).persisted_dict()
    result = await apply_handle(
        {"repaired_config": repaired_payload},
        _mk_ctx(tmp_path, config=in_memory),
    )

    assert isinstance(result, ToolResult)
    assert target.exists()
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk["active_domain"] == "research"
    assert on_disk["web_port"] == 5500
    assert result.data is not None
    assert result.data["status"] == "applied"


async def test_apply_rejects_malformed_payload(tmp_path: Path) -> None:
    """Pydantic-invalid payloads raise ValueError before any disk write."""
    target = tmp_path / ".brain" / "config.json"
    with pytest.raises((ValueError, Exception)):
        await apply_handle(
            {"repaired_config": {"web_port": "not an int"}},
            _mk_ctx(tmp_path, config=Config()),
        )
    assert not target.exists()


async def test_apply_requires_repaired_config_arg(tmp_path: Path) -> None:
    """Missing ``repaired_config`` arg raises a clear error."""
    with pytest.raises((KeyError, TypeError, ValueError)):
        await apply_handle({}, _mk_ctx(tmp_path, config=Config()))


async def test_apply_mutates_in_memory_config(tmp_path: Path) -> None:
    """After apply, ctx.config reflects the repaired payload (in-place mutation).

    Mirrors :func:`persist_config_or_revert`'s contract: ToolContext is
    frozen, so the helper mutates field-by-field. The frontend's diff
    state then collapses (subsequent calls to repair_config see no diff).
    """
    in_memory = Config(active_domain="research")
    repaired_payload = Config(active_domain="research", web_port=4242).persisted_dict()
    ctx = _mk_ctx(tmp_path, config=in_memory)

    await apply_handle({"repaired_config": repaired_payload}, ctx)

    # After apply, the live Config carries the repaired values.
    assert ctx.config.web_port == 4242


async def test_apply_registered_in_tool_registry() -> None:
    """Both new tools must auto-register at import time (per the project pattern)."""
    import brain_core.tools as tools_registry

    names = [m.NAME for m in tools_registry.list_tools()]
    assert "brain_repair_config" in names
    assert "brain_repair_config_apply" in names
