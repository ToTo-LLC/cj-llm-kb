"""Plan 22 T5 — pin tests for ``brain_core.tools.list_orphans``.

Pins:

* INPUT_SCHEMA shape — only an optional ``folder`` filter, no required keys.
* ToolResult.data shape (``{orphans: [{note_path, domain, source_path,
  orphaned_at, watched_folder_id}]}``).
* Branch coverage: empty vault, mix of orphan/non-orphan notes, folder
  filter narrows the list.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_orphans import INPUT_SCHEMA, NAME, handle
from brain_core.vault.frontmatter import serialize_with_frontmatter
from brain_core.vault.paths import _orphan_cache_clear


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
    orphaned: bool,
    watched_folder_id: str | None = None,
    source_path: str | None = None,
) -> Path:
    note_dir = vault / domain / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    fm: dict[str, object] = {
        "title": slug,
        "domain": domain,
        "type": "source",
    }
    if orphaned:
        fm["orphaned"] = True
        fm["orphaned_at"] = "2026-05-01"
    if watched_folder_id is not None:
        fm["watched_folder_id"] = watched_folder_id
    if source_path is not None:
        fm["source_path"] = source_path
    note_path = note_dir / f"{slug}.md"
    note_path.write_text(
        serialize_with_frontmatter(fm, body="# body\n"), encoding="utf-8"
    )
    return note_path


def test_name() -> None:
    assert NAME == "brain_list_orphans"


def test_input_schema_shape() -> None:
    """INPUT_SCHEMA pins the optional folder filter shape."""
    assert INPUT_SCHEMA == {
        "type": "object",
        "properties": {
            "folder": {
                "type": ["string", "null"],
                "description": (
                    "Optional watched-folder path filter. When set, only orphans "
                    "whose frontmatter watched_folder_id matches this value are returned."
                ),
            },
        },
    }


async def test_empty_vault_returns_empty_orphans(tmp_path: Path) -> None:
    _orphan_cache_clear()
    cfg = Config(domains=["research", "personal"], active_domain="research")
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data == {"orphans": []}


async def test_returns_only_orphaned_notes_data_shape_pin(tmp_path: Path) -> None:
    """Pin every key on the per-orphan dict."""
    _orphan_cache_clear()
    cfg = Config(domains=["research", "personal"], active_domain="research")
    _seed_note(
        vault=tmp_path, domain="research", slug="alive",
        orphaned=False,
    )
    orphan = _seed_note(
        vault=tmp_path, domain="research", slug="dead",
        orphaned=True,
        watched_folder_id="/tmp/watch-X",
        source_path="/tmp/watch-X/dead.txt",
    )
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))
    assert result.data is not None
    orphans = result.data["orphans"]
    assert len(orphans) == 1
    entry = orphans[0]
    assert set(entry.keys()) == {
        "note_path",
        "domain",
        "source_path",
        "orphaned_at",
        "watched_folder_id",
    }
    assert entry["note_path"] == str(orphan)
    assert entry["domain"] == "research"
    assert entry["source_path"] == "/tmp/watch-X/dead.txt"
    assert entry["orphaned_at"] == "2026-05-01"
    assert entry["watched_folder_id"] == "/tmp/watch-X"


async def test_folder_filter_narrows_list(tmp_path: Path) -> None:
    _orphan_cache_clear()
    cfg = Config(domains=["research", "personal"], active_domain="research")
    _seed_note(
        vault=tmp_path, domain="research", slug="orph-a",
        orphaned=True, watched_folder_id="/tmp/folder-A",
    )
    _seed_note(
        vault=tmp_path, domain="research", slug="orph-b",
        orphaned=True, watched_folder_id="/tmp/folder-B",
    )
    result = await handle({"folder": "/tmp/folder-A"}, _mk_ctx(tmp_path, config=cfg))
    assert result.data is not None
    orphans = result.data["orphans"]
    assert len(orphans) == 1
    assert orphans[0]["watched_folder_id"] == "/tmp/folder-A"
