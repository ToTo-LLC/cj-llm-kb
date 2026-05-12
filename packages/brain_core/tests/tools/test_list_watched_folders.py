"""Plan 22 T5 — pin tests for ``brain_core.tools.list_watched_folders``.

Pins:

* INPUT_SCHEMA shape (no required keys, no properties).
* ToolResult.data shape (``{folders: [{path, domain, enabled,
  last_sync, policy, include_subdirs, file_count, orphan_count}]}``).
* Branch coverage: empty config, single watched folder, file/orphan
  counting from frontmatter.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.config.schema import Config, WatchedFolder
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_watched_folders import INPUT_SCHEMA, NAME, handle
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


def _seed_note(
    *,
    vault: Path,
    domain: str,
    slug: str,
    watched_folder_id: str | None,
    orphaned: bool = False,
) -> Path:
    note_dir = vault / domain / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    fm: dict[str, object] = {
        "title": slug,
        "domain": domain,
        "type": "source",
    }
    if watched_folder_id is not None:
        fm["watched_folder_id"] = watched_folder_id
    if orphaned:
        fm["orphaned"] = True
        fm["orphaned_at"] = "2026-05-01"
    note_path = note_dir / f"{slug}.md"
    note_path.write_text(
        serialize_with_frontmatter(fm, body="# body\n"), encoding="utf-8"
    )
    return note_path


def test_name() -> None:
    assert NAME == "brain_list_watched_folders"


def test_input_schema_shape() -> None:
    """INPUT_SCHEMA pins the no-arg contract."""
    assert INPUT_SCHEMA == {"type": "object", "properties": {}}


async def test_empty_config_returns_empty_list(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data == {"folders": []}


async def test_data_shape_pin_with_one_folder(tmp_path: Path) -> None:
    """Pin every key on the per-entry dict."""
    folder_str = "/tmp/test-watch-A"
    wf = WatchedFolder(
        path=folder_str, domain="research", include_subdirs=True
    )
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))
    assert result.data is not None
    folders = result.data["folders"]
    assert len(folders) == 1
    entry = folders[0]
    assert set(entry.keys()) == {
        "path",
        "domain",
        "enabled",
        "last_sync",
        "policy",
        "include_subdirs",
        "file_count",
        "orphan_count",
    }
    assert entry["path"] == folder_str
    assert entry["domain"] == "research"
    assert entry["enabled"] is True
    assert entry["last_sync"] is None
    assert entry["policy"] == "overwrite"
    assert entry["include_subdirs"] is True
    assert entry["file_count"] == 0
    assert entry["orphan_count"] == 0


async def test_file_and_orphan_counts_from_frontmatter(tmp_path: Path) -> None:
    folder_str = "/tmp/test-watch-B"
    wf = WatchedFolder(path=folder_str, domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    # Seed 3 notes attributed to the folder; 2 orphaned.
    _seed_note(
        vault=tmp_path, domain="research", slug="a",
        watched_folder_id=folder_str, orphaned=False,
    )
    _seed_note(
        vault=tmp_path, domain="research", slug="b",
        watched_folder_id=folder_str, orphaned=True,
    )
    _seed_note(
        vault=tmp_path, domain="research", slug="c",
        watched_folder_id=folder_str, orphaned=True,
    )
    # And a note NOT attributed to the folder — should be ignored.
    _seed_note(
        vault=tmp_path, domain="research", slug="z",
        watched_folder_id=None, orphaned=False,
    )
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))
    assert result.data is not None
    entry = result.data["folders"][0]
    assert entry["file_count"] == 3
    assert entry["orphan_count"] == 2
