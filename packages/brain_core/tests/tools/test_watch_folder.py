"""Plan 22 T5 + T9 — pin tests for ``brain_core.tools.watch_folder``.

T5 pins (initial set):

* INPUT_SCHEMA shape (4 properties, only ``folder`` required).
* ToolResult.data shape for both ``initial_sync=False`` (no pipeline
  needed) and ``already_watched`` branches.
* Cross-field domain pre-check: passing a domain not in
  ``Config.domains`` raises ``ValueError`` BEFORE the append, per the
  Plan 16 T36 pre-check pattern.
* Branch coverage: missing folder, non-absolute folder, already-watched
  idempotency, full happy path with ``initial_sync=False``.

T9 pins (Plan 22 T9 — backup trigger swap + initial-sync cost estimate):

* ``backup.py`` / ``backup_create.py`` expose the new trigger value
  ``"pre_watched_folder_sync"`` in ``_VALID_TRIGGERS``.
* The watch tool calls ``create_snapshot`` with
  ``trigger="pre_watched_folder_sync"`` (NOT the T5 ``"manual"`` stub).
* ``_estimate_initial_sync_cost`` computes tokens as
  ``file_count × _CLASSIFY_TOKEN_COST``.
* ``ToolResult.text`` and ``ToolResult.data["cost_estimate"]`` surface
  the projected spend when ``initial_sync=True``; D3 says NO refusal —
  the estimate is informational and the call goes through.

The ``initial_sync=True`` happy path needs a wired ``BulkImporter``;
T9's tests use the same ``_FakeBulkImporter`` pattern as
``test_bulk_import.py`` to drive the initial-sync branch without
LLMs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from brain_core.config.schema import Config, WatchedFolder
from brain_core.ingest.bulk import BulkPlan
from brain_core.ingest.types import IngestResult
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.watch_folder import (
    INPUT_SCHEMA,
    NAME,
    _CLASSIFY_MAX_OUTPUT_TOKENS,
    _CLASSIFY_TOKEN_COST,
    _estimate_initial_sync_cost,
    handle,
)


def _mk_ctx(vault: Path, *, config: Config | None = None) -> ToolContext:
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


def test_name() -> None:
    assert NAME == "brain_watch_folder"


def test_input_schema_shape() -> None:
    """Pin the INPUT_SCHEMA's property set + required key."""
    assert INPUT_SCHEMA["type"] == "object"
    assert set(INPUT_SCHEMA["properties"].keys()) == {
        "folder",
        "domain",
        "include_subdirs",
        "initial_sync",
    }
    assert INPUT_SCHEMA["required"] == ["folder"]
    assert INPUT_SCHEMA["properties"]["folder"]["type"] == "string"
    assert INPUT_SCHEMA["properties"]["domain"]["type"] == ["string", "null"]
    assert INPUT_SCHEMA["properties"]["include_subdirs"]["default"] is True
    assert INPUT_SCHEMA["properties"]["initial_sync"]["default"] is True


async def test_refuses_relative_folder(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    with pytest.raises(ValueError, match="absolute"):
        await handle(
            {"folder": "relative/path", "initial_sync": False},
            _mk_ctx(tmp_path, config=cfg),
        )
    assert len(cfg.watched_folders) == 0


async def test_refuses_missing_folder(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    with pytest.raises(FileNotFoundError):
        await handle(
            {"folder": str(tmp_path / "ghost"), "initial_sync": False},
            _mk_ctx(tmp_path, config=cfg),
        )
    assert len(cfg.watched_folders) == 0


async def test_refuses_orphan_domain_per_plan_16_t36(tmp_path: Path) -> None:
    """Cross-field pre-check: domain not in Config.domains raises before
    append. The Pydantic model_validator on Config would also fire on
    save, but the pre-check is the canonical pattern (per Plan 16 T36)
    that prevents the orphan from landing on the live Config in the
    first place."""
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "watch-me"
    folder.mkdir()
    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {
                "folder": str(folder),
                "domain": "nonexistent",
                "initial_sync": False,
            },
            _mk_ctx(tmp_path, config=cfg),
        )
    # The orphan domain never landed on the live Config.
    assert len(cfg.watched_folders) == 0


async def test_data_shape_pin_initial_sync_false(tmp_path: Path) -> None:
    """Pin the response shape when initial_sync=False (no pipeline needed).

    The 5-key data shape MUST be ``{status, folder, domain,
    initial_sync_summary, cost_estimate}`` per the plan-doc. Plan 22 T9
    added ``cost_estimate``; it is ``None`` when ``initial_sync=False``
    because the estimate only applies to the initial-sync path.
    """
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "watch-me"
    folder.mkdir()
    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {
        "status",
        "folder",
        "domain",
        "initial_sync_summary",
        "cost_estimate",
    }
    assert result.data["status"] == "watched"
    assert result.data["folder"] == str(folder)
    assert result.data["domain"] == "research"
    assert result.data["initial_sync_summary"] is None
    assert result.data["cost_estimate"] is None
    # Append landed on the live config.
    assert len(cfg.watched_folders) == 1
    assert cfg.watched_folders[0].path == str(folder)
    assert cfg.watched_folders[0].domain == "research"


async def test_already_watched_returns_idempotent_status(tmp_path: Path) -> None:
    """Calling brain_watch_folder twice on the same path is a no-op:
    the second call returns status=already_watched without re-syncing."""
    folder = tmp_path / "watch-me"
    folder.mkdir()
    existing = WatchedFolder(path=str(folder), domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[existing],
    )
    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": True,  # would normally trigger backup + bulk
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert result.data is not None
    assert result.data["status"] == "already_watched"
    assert result.data["folder"] == str(folder)
    assert result.data["domain"] == "research"
    assert result.data["initial_sync_summary"] is None
    # Cost estimate is None on the already_watched short-circuit — no
    # initial sync runs, so there is no spend to project (Plan 22 T9).
    assert result.data["cost_estimate"] is None
    # No duplicate entry was appended.
    assert len(cfg.watched_folders) == 1


async def test_persists_to_disk(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "watch-persist"
    folder.mkdir()
    await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    config_path = tmp_path / ".brain" / "config.json"
    assert config_path.exists()
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert len(on_disk["watched_folders"]) == 1
    assert on_disk["watched_folders"][0]["path"] == str(folder)
    assert on_disk["watched_folders"][0]["domain"] == "research"


# ---------------------------------------------------------------------------
# Plan 22 T9 — backup trigger swap + initial-sync cost estimate pin tests.
# ---------------------------------------------------------------------------


def test_pre_watched_folder_sync_in_backup_create_valid_triggers() -> None:
    """T9 pin: ``backup_create._VALID_TRIGGERS`` includes the new trigger.

    Catches a forgotten extension of the tool-surface tuple if a future
    refactor regroups the constants.
    """
    from brain_core.tools.backup_create import _VALID_TRIGGERS

    assert "pre_watched_folder_sync" in _VALID_TRIGGERS


def test_pre_watched_folder_sync_in_backup_module_valid_triggers() -> None:
    """T9 pin: ``backup._VALID_TRIGGERS`` (source of truth) includes the
    new trigger. The frontend regex + ``BackupTrigger`` Literal stay in
    sync with the tool surface — drift between the two would let the
    tool accept a value the snapshot writer rejects.
    """
    from brain_core.backup import _FILENAME_RE, _VALID_TRIGGERS

    assert "pre_watched_folder_sync" in _VALID_TRIGGERS
    # The filename regex must also match the new trigger so existing
    # snapshots are listed correctly by brain_backup_list.
    assert _FILENAME_RE.match(
        "20260512T120000123456-pre_watched_folder_sync.tar.gz"
    ) is not None


def test_estimate_initial_sync_cost_token_calc(tmp_path: Path) -> None:
    """T9 pin: token estimate equals ``file_count × _CLASSIFY_TOKEN_COST``
    and the USD estimate respects the configured pricing entry.

    Catches drift if the per-file budget changes without a corresponding
    update to ``bulk_import._CLASSIFY_TOKEN_COST`` (both modules MUST
    project the same per-file classifier spend).
    """
    folder = tmp_path / "sync-source"
    folder.mkdir()
    for i in range(7):
        (folder / f"note-{i}.txt").write_text("hello", encoding="utf-8")
    # Hidden + symlink files don't count (rglob still yields them but
    # is_symlink + is_file filtering excludes); add a control sample.
    (folder / ".hidden").write_text("ignored", encoding="utf-8")

    file_count, tokens, usd = _estimate_initial_sync_cost(
        folder, classify_model="claude-haiku-4-5-20251001"
    )
    # rglob("*") DOES yield the .hidden file (it's a regular file), so
    # the count is 8 — the helper does not filter dotfiles. The
    # ``BulkImporter.plan`` walker has its own dotfile skipping, but
    # the cost estimate is a CONSERVATIVE projection so an over-count
    # is acceptable; under-count would be a bug.
    assert file_count == 8
    assert tokens == 8 * _CLASSIFY_TOKEN_COST
    # Haiku pricing: $1.0 input + $5.0 output per million tokens.
    # 8 * 1000 = 8000 input tokens; 8 * 256 = 2048 output tokens.
    # Cost = (8000 / 1e6) * 1.0 + (2048 / 1e6) * 5.0
    #      = 0.008 + 0.01024 = 0.01824 USD
    expected = (8 * _CLASSIFY_TOKEN_COST / 1_000_000) * 1.0 + (
        8 * _CLASSIFY_MAX_OUTPUT_TOKENS / 1_000_000
    ) * 5.0
    assert usd is not None
    assert abs(usd - expected) < 1e-9


def test_estimate_initial_sync_cost_unknown_model_returns_none(
    tmp_path: Path,
) -> None:
    """T9 pin: an unknown classify model leaves estimated_usd=None
    (forward-compat: a model swap that lands ahead of pricing shouldn't
    raise — the tokens still surface)."""
    folder = tmp_path / "sync-source"
    folder.mkdir()
    (folder / "note.txt").write_text("x", encoding="utf-8")

    file_count, tokens, usd = _estimate_initial_sync_cost(
        folder, classify_model="future-model-with-no-pricing-row"
    )
    assert file_count == 1
    assert tokens == _CLASSIFY_TOKEN_COST
    assert usd is None


# Fake BulkImporter mirroring ``test_bulk_import._FakeBulkImporter`` — keeps
# the T9 happy-path tests from needing a real classifier / pipeline.
class _FakeBulkImporter:
    def __init__(self, *_a: Any, **_kw: Any) -> None:
        pass

    async def plan(self, *_a: Any, **_kw: Any) -> BulkPlan:
        return BulkPlan()

    async def apply(self, *_a: Any, **_kw: Any) -> list[IngestResult]:
        return []


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Wire fakes for BulkImporter + _build_pipeline + create_snapshot.

    Returns the snapshot-call-arg-capture list so tests can assert the
    trigger string passed to ``create_snapshot``.
    """
    snapshot_calls: list[dict[str, Any]] = []

    def _fake_snapshot(vault_root: Path, *, trigger: str) -> Any:
        snapshot_calls.append({"vault_root": vault_root, "trigger": trigger})
        # Mimic a successful snapshot — the watch_folder body discards
        # the return value (best-effort backup).
        return object()

    monkeypatch.setattr(
        "brain_core.tools.watch_folder.BulkImporter", _FakeBulkImporter
    )
    monkeypatch.setattr(
        "brain_core.tools.watch_folder._build_pipeline",
        lambda _ctx: object(),
    )
    monkeypatch.setattr(
        "brain_core.tools.watch_folder.create_snapshot", _fake_snapshot
    )
    return snapshot_calls


async def test_initial_sync_calls_backup_with_pre_watched_folder_sync_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9 pin: the watch tool invokes ``create_snapshot`` with
    ``trigger="pre_watched_folder_sync"`` BEFORE the initial-sync bulk
    import. The trigger string is greppable — a future refactor that
    accidentally reverts to the T5 ``"manual"`` stub trips this pin.
    """
    snapshot_calls = _install_fakes(monkeypatch)
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "watch-and-sync"
    folder.mkdir()
    (folder / "note.txt").write_text("hello", encoding="utf-8")

    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": True,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert isinstance(result, ToolResult)
    assert len(snapshot_calls) == 1
    assert snapshot_calls[0]["trigger"] == "pre_watched_folder_sync"
    assert snapshot_calls[0]["vault_root"] == tmp_path


async def test_initial_sync_surfaces_cost_estimate_in_text_and_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9 pin: ToolResult.text contains the cost-estimate readout AND
    ToolResult.data["cost_estimate"] has the four-key projection
    payload. Per D3 the estimate is informational only — the call goes
    through regardless of file count.
    """
    _install_fakes(monkeypatch)
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "cost-est"
    folder.mkdir()
    # 5 files keeps the cost estimate small + predictable.
    for i in range(5):
        (folder / f"f-{i}.txt").write_text("hello", encoding="utf-8")

    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": True,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert result.data is not None
    # data shape: cost_estimate has 4 keys.
    cost_est = result.data["cost_estimate"]
    assert cost_est is not None
    assert set(cost_est.keys()) == {
        "file_count",
        "estimated_tokens",
        "estimated_usd",
        "classify_model",
    }
    assert cost_est["file_count"] == 5
    assert cost_est["estimated_tokens"] == 5 * _CLASSIFY_TOKEN_COST
    assert cost_est["estimated_usd"] is not None
    # classify_model falls back to the haiku constant when no Config.llm
    # is configured on the test fixture.
    assert cost_est["classify_model"] == "claude-haiku-4-5-20251001"
    # text contains the readout — the user sees this in the CLI / MCP /
    # API response. Two anchor phrases pin the wording.
    assert "initial sync estimate" in result.text
    assert "5 files" in result.text
    assert "classify only" in result.text


async def test_initial_sync_does_not_refuse_on_large_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9 pin (D3): there is NO refusal threshold on the initial-sync
    cost estimate. A folder with hundreds of files surfaces a large
    estimate but the call still goes through — rate-limit + per-domain
    budget caps elsewhere remain the hard ceilings.
    """
    _install_fakes(monkeypatch)
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "huge-folder"
    folder.mkdir()
    # 200 files would trip ``bulk_import._LARGE_FOLDER_THRESHOLD`` if
    # this routed through brain_bulk_import — proving T9's path does
    # NOT inherit that refusal.
    for i in range(200):
        (folder / f"f-{i}.txt").write_text("x", encoding="utf-8")

    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": True,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert result.data is not None
    assert result.data["status"] == "watched"
    assert result.data["cost_estimate"] is not None
    assert result.data["cost_estimate"]["file_count"] == 200
    # The folder is fully watched — no "refused" status leaks through.
    assert "refused" not in result.text.lower()


async def test_cost_estimate_omitted_when_initial_sync_false(
    tmp_path: Path,
) -> None:
    """T9 pin: ``initial_sync=False`` leaves ``cost_estimate=None`` (no
    spend to project). text omits the cost-estimate readout to keep
    the no-sync path concise.
    """
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "no-sync"
    folder.mkdir()
    (folder / "note.txt").write_text("x", encoding="utf-8")
    result = await handle(
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
        _mk_ctx(tmp_path, config=cfg),
    )
    assert result.data is not None
    assert result.data["cost_estimate"] is None
    assert "initial sync estimate" not in result.text
