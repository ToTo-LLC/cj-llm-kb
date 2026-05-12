"""Plan 22 T5 — pin tests for ``brain_core.tools.resync_folder``.

Pins:

* INPUT_SCHEMA shape (``folder`` required, no other properties).
* ToolResult.data shape (``{status, folder, summary: {updated,
  no_change, newly_orphaned, restored_from_orphan}}``).
* Branch coverage: missing folder, non-absolute folder, unwatched
  folder (refused), empty-folder happy path (no walks needed → no
  pipeline LLM activity).

Full pipeline-integrated resync coverage (update / overwrite / orphan-
restore on source-reappear) is exercised by the brain_core integration
tests for ``IngestPipeline.update_source`` and ``mark_orphaned`` (T2 /
T3 fixtures) — this T5 file pins the tool's contract on top of those.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config, WatchedFolder
from brain_core.llm.fake import FakeLLMProvider
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.resync_folder import INPUT_SCHEMA, NAME, handle
from brain_core.vault.writer import VaultWriter


def _mk_ctx(vault: Path, *, config: Config | None = None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=VaultWriter(vault_root=vault),
        llm=FakeLLMProvider(),
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=config,
    )


def test_name() -> None:
    assert NAME == "brain_resync_folder"


def test_input_schema_shape() -> None:
    assert INPUT_SCHEMA == {
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Absolute path of the watched folder to resync.",
            },
        },
        "required": ["folder"],
    }


async def test_refuses_relative_folder(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    with pytest.raises(ValueError, match="absolute"):
        await handle({"folder": "rel/path"}, _mk_ctx(tmp_path, config=cfg))


async def test_refuses_missing_folder(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"], active_domain="research")
    with pytest.raises(FileNotFoundError):
        await handle(
            {"folder": str(tmp_path / "ghost")},
            _mk_ctx(tmp_path, config=cfg),
        )


async def test_refuses_unwatched_folder(tmp_path: Path) -> None:
    """Resync only makes sense on a folder the user has opted into
    watching. Calling on an unwatched folder is a programmer error."""
    cfg = Config(domains=["research", "personal"], active_domain="research")
    folder = tmp_path / "not-watched"
    folder.mkdir()
    with pytest.raises(ValueError, match="not in Config.watched_folders"):
        await handle({"folder": str(folder)}, _mk_ctx(tmp_path, config=cfg))


async def test_data_shape_pin_empty_folder(tmp_path: Path) -> None:
    """Empty folder: no walked files, no vault notes attributed to it,
    all four summary counts are zero. Pins the response shape without
    needing the pipeline to run any LLM calls."""
    folder = tmp_path / "watched-empty"
    folder.mkdir()
    wf = WatchedFolder(path=str(folder), domain="research")
    cfg = Config(
        domains=["research", "personal"],
        active_domain="research",
        watched_folders=[wf],
    )
    result = await handle({"folder": str(folder)}, _mk_ctx(tmp_path, config=cfg))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "folder", "summary"}
    assert result.data["status"] == "resynced"
    assert result.data["folder"] == str(folder)
    summary = result.data["summary"]
    assert set(summary.keys()) == {
        "updated",
        "no_change",
        "newly_orphaned",
        "restored_from_orphan",
    }
    assert summary == {
        "updated": 0,
        "no_change": 0,
        "newly_orphaned": 0,
        "restored_from_orphan": 0,
    }
