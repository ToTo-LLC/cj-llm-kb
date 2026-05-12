"""Plan 22 T5 — pin tests for ``brain_core.tools.unwatch_folder``.

Pins:

* INPUT_SCHEMA shape (``folder`` required).
* ToolResult.data shape — both happy path (``status=unwatched``) and
  idempotent path (``status=not_watched``).
* Branch coverage: matched / unmatched / persistence side-effect.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.config.schema import Config, WatchedFolder
import json
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.unwatch_folder import INPUT_SCHEMA, NAME, handle
from brain_core.vault.frontmatter import serialize_with_frontmatter


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
    assert NAME == "brain_unwatch_folder"


def test_input_schema_shape() -> None:
    assert INPUT_SCHEMA == {
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Absolute path of the folder to stop watching.",
            },
        },
        "required": ["folder"],
    }


async def test_data_shape_pin_when_unwatched(tmp_path: Path) -> None:
    folder = "/tmp/test-watch"
    wf = WatchedFolder(path=folder, domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    result = await handle({"folder": folder}, _mk_ctx(tmp_path, config=cfg))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "folder", "remaining_notes"}
    assert result.data["status"] == "unwatched"
    assert result.data["folder"] == folder
    assert result.data["remaining_notes"] == 0
    # In-memory config mutation landed.
    assert len(cfg.watched_folders) == 0


async def test_data_shape_pin_when_not_watched(tmp_path: Path) -> None:
    """Idempotent — calling on a folder that isn't watched returns
    status=not_watched rather than raising."""
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[],
    )
    result = await handle(
        {"folder": "/tmp/not-watched"}, _mk_ctx(tmp_path, config=cfg)
    )
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "folder", "remaining_notes"}
    assert result.data["status"] == "not_watched"
    assert result.data["folder"] == "/tmp/not-watched"
    assert result.data["remaining_notes"] == 0


async def test_persists_removal_to_disk(tmp_path: Path) -> None:
    folder = "/tmp/test-watch-disk"
    wf = WatchedFolder(path=folder, domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    await handle({"folder": folder}, _mk_ctx(tmp_path, config=cfg))
    # Confirm persistence — config.json on disk has no watched_folders.
    config_path = tmp_path / ".brain" / "config.json"
    assert config_path.exists()
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert on_disk.get("watched_folders", []) == []


async def test_counts_remaining_linked_notes(tmp_path: Path) -> None:
    folder = "/tmp/test-watch-counts"
    wf = WatchedFolder(path=folder, domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    # Seed two notes that link back to the folder.
    note_dir = tmp_path / "research" / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    for slug in ("a", "b"):
        fm = {
            "title": slug,
            "domain": "research",
            "type": "source",
            "watched_folder_id": folder,
        }
        (note_dir / f"{slug}.md").write_text(
            serialize_with_frontmatter(fm, body="# x\n"), encoding="utf-8"
        )
    result = await handle({"folder": folder}, _mk_ctx(tmp_path, config=cfg))
    assert result.data is not None
    assert result.data["remaining_notes"] == 2
