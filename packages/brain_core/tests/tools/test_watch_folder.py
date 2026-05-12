"""Plan 22 T5 — pin tests for ``brain_core.tools.watch_folder``.

Pins:

* INPUT_SCHEMA shape (4 properties, only ``folder`` required).
* ToolResult.data shape for both ``initial_sync=False`` (no pipeline
  needed) and ``already_watched`` branches.
* Cross-field domain pre-check: passing a domain not in
  ``Config.domains`` raises ``ValueError`` BEFORE the append, per the
  Plan 16 T36 pre-check pattern.
* Branch coverage: missing folder, non-absolute folder, already-watched
  idempotency, full happy path with ``initial_sync=False``.

The ``initial_sync=True`` happy path requires a wired
``BulkImporter`` (classify + summarize + integrate). That coverage lives
in the integration test (Plan 22 T6+); T5's tests pin the unit-level
contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.schema import Config, WatchedFolder
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.watch_folder import INPUT_SCHEMA, NAME, handle


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

    The 4-key data shape MUST be ``{status, folder, domain,
    initial_sync_summary}`` per the plan-doc.
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
    }
    assert result.data["status"] == "watched"
    assert result.data["folder"] == str(folder)
    assert result.data["domain"] == "research"
    assert result.data["initial_sync_summary"] is None
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
