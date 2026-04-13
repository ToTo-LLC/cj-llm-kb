from __future__ import annotations

from pathlib import Path

from brain_core.vault.types import Edit, IndexEntryPatch, NewFile, PatchSet


def test_patchset_totals() -> None:
    ps = PatchSet(
        new_files=[NewFile(path=Path("/tmp/a.md"), content="x" * 100)],
        edits=[Edit(path=Path("/tmp/b.md"), old="o", new="nn")],
        index_entries=[IndexEntryPatch(section="Sources", line="- [[x]] — y", domain="research")],
        log_entry="## [...]",
        reason="test",
    )
    assert ps.total_size() == 102  # 100 + len("nn")
    assert ps.file_count() == 2  # two distinct paths
    assert len(ps.index_entries) == 1


def test_patchset_empty_defaults() -> None:
    ps = PatchSet()
    assert ps.new_files == []
    assert ps.edits == []
    assert ps.index_entries == []
    assert ps.log_entry is None
    assert ps.reason == ""
    assert ps.total_size() == 0
    assert ps.file_count() == 0
