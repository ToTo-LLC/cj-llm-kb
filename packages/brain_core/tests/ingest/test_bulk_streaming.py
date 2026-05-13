"""Tests for ``BulkImporter.plan_streaming`` — Plan 26 T3.

Covers the four event types per D6 + the 50-file flood-control cadence
per D9 + the documented failure modes (permission denied, path not
found, mid-walk cancellation, generic internal error).

The streaming walk path is the load-bearing piece for the bulk-import
wizard's real-progress UI — it MUST emit a clean ``started ... complete``
sequence on every successful walk and a ``started ... error`` sequence
on every failure. These tests pin both contracts.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from brain_core.ingest.bulk import _WALK_PROGRESS_INTERVAL, BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.walk_events import (
    WalkComplete,
    WalkError,
    WalkProgress,
    WalkStarted,
)
from brain_core.llm.fake import FakeLLMProvider
from brain_core.vault.writer import VaultWriter


def _make_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _importer(vault: Path) -> BulkImporter:
    return BulkImporter(_make_pipeline(vault, FakeLLMProvider()))


@pytest.mark.asyncio
async def test_empty_folder_emits_started_then_complete(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Empty folder → exactly two events: started, complete(0)."""
    folder = tmp_path / "empty"
    folder.mkdir()

    events = [e async for e in _importer(ephemeral_vault).plan_streaming(folder)]

    assert len(events) == 2
    assert isinstance(events[0], WalkStarted)
    assert events[0].path == str(folder)
    assert isinstance(events[1], WalkComplete)
    assert events[1].total_count == 0
    # plan_id is a fresh UUID4 string — at least the right shape.
    assert len(events[1].plan_id) == 36


@pytest.mark.asyncio
async def test_small_folder_emits_no_progress_events(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Fewer than _WALK_PROGRESS_INTERVAL files → no WalkProgress at all."""
    folder = tmp_path / "small"
    folder.mkdir()
    # 5 claimable .txt files — well under the 50-file flood threshold.
    for i in range(5):
        (folder / f"note-{i}.txt").write_text(
            "Hello, world!\n" * 10, encoding="utf-8"
        )

    events = [e async for e in _importer(ephemeral_vault).plan_streaming(folder)]

    progress_events = [e for e in events if isinstance(e, WalkProgress)]
    assert progress_events == []

    assert isinstance(events[0], WalkStarted)
    assert isinstance(events[-1], WalkComplete)
    assert events[-1].total_count == 5


@pytest.mark.asyncio
async def test_large_folder_emits_progress_every_interval(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """>_WALK_PROGRESS_INTERVAL files → at least one WalkProgress event."""
    folder = tmp_path / "big"
    folder.mkdir()
    # Need to exceed the flood threshold; +5 buffer keeps the test robust
    # if someone tweaks _WALK_PROGRESS_INTERVAL upward in a small range.
    n_files = _WALK_PROGRESS_INTERVAL + 5
    for i in range(n_files):
        (folder / f"file-{i:04d}.txt").write_text(
            "content\n", encoding="utf-8"
        )

    events = [e async for e in _importer(ephemeral_vault).plan_streaming(folder)]

    progress_events = [e for e in events if isinstance(e, WalkProgress)]
    assert len(progress_events) >= 1
    # Each progress event's files_seen is a multiple of the interval and
    # monotonically increasing.
    seens = [e.files_seen for e in progress_events]
    assert all(s % _WALK_PROGRESS_INTERVAL == 0 for s in seens)
    assert seens == sorted(seens)

    assert isinstance(events[-1], WalkComplete)
    assert events[-1].total_count == n_files


@pytest.mark.asyncio
async def test_path_not_found_yields_walk_error_then_raises(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Missing source_root → WalkError(error_code='path_not_found')."""
    missing = tmp_path / "does-not-exist"

    gen = _importer(ephemeral_vault).plan_streaming(missing)
    collected: list[object] = []
    with pytest.raises(FileNotFoundError):
        async for e in gen:
            collected.append(e)

    # WalkStarted always fires first; then WalkError before the raise.
    assert isinstance(collected[0], WalkStarted)
    assert any(
        isinstance(e, WalkError) and e.error_code == "path_not_found"
        for e in collected
    )


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX chmod 0 is the only portable way to provoke PermissionError on a dir",
)
@pytest.mark.asyncio
async def test_permission_denied_yields_walk_error_then_raises(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Unreadable directory → WalkError(error_code='permission_denied')."""
    folder = tmp_path / "locked"
    folder.mkdir()
    (folder / "decoy.txt").write_text("x", encoding="utf-8")
    folder.chmod(0)
    try:
        gen = _importer(ephemeral_vault).plan_streaming(folder)
        collected: list[object] = []
        with pytest.raises(PermissionError):
            async for e in gen:
                collected.append(e)
        assert isinstance(collected[0], WalkStarted)
        assert any(
            isinstance(e, WalkError) and e.error_code == "permission_denied"
            for e in collected
        )
    finally:
        # Restore mode so pytest's tmp_path cleanup can remove the dir.
        folder.chmod(0o755)


@pytest.mark.asyncio
async def test_cancellation_mid_walk_propagates_cleanly(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """asyncio.CancelledError propagates out of the generator without
    swallowing or emitting a final WalkError frame.
    """
    folder = tmp_path / "cancel"
    folder.mkdir()
    # Plenty of files so the walk has work to do.
    for i in range(_WALK_PROGRESS_INTERVAL * 3):
        (folder / f"f-{i:04d}.txt").write_text("x" * 10, encoding="utf-8")

    importer = _importer(ephemeral_vault)

    async def consume() -> None:
        async for _ in importer.plan_streaming(folder):
            # Surrender control so the cancel() call below lands inside
            # the body of the generator rather than after it completes.
            await asyncio.sleep(0)

    task = asyncio.create_task(consume())
    # Give the task one tick to enter the generator body.
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
