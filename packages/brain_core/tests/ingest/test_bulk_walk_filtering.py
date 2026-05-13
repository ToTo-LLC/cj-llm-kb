"""Tests for BulkImporter walk-stage filtering. Plan 25 T1.

Covers:
- ``_SYSTEM_FILES`` denylist (Mac / Windows / Linux / dev artifacts).
- Pattern-based system-file matches (``._*``, ``.Trash-*``, ``~$*``).
- ``_VALID_EXTENSIONS`` unsupported-type pre-filter.
- Ancestor-path system-directory exclusion (e.g. file deep in
  ``__MACOSX/``).
- Interaction with the existing ``_is_hidden`` dotfile check.

Filtered files are SILENTLY skipped — they appear neither in
``plan.items`` nor in ``plan.skipped``. Only files that pass the
extension filter but fail dispatch (e.g. an unclaimed but
whitelisted extension) land in ``skipped``.

Tests use ``FakeLLMProvider`` with canned classify responses for the
``items`` they expect to land in the plan.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.bulk import BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.llm.fake import FakeLLMProvider
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLASSIFY_RESEARCH = '{"source_type":"text","domain":"research","confidence":0.9}'


def _make_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _real_text(folder: Path, name: str = "real.txt") -> Path:
    """Write a single claimable .txt file. Used as the positive control."""
    p = folder / name
    p.write_text("Hello, world!\n" * 30, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1 — .DS_Store filtered (exact match, Mac)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dsstore_filtered(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    (folder / ".DS_Store").write_bytes(b"\x00\x01\x02")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 2 — Thumbs.db filtered (exact match, Windows)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbs_db_filtered(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    (folder / "Thumbs.db").write_bytes(b"\x00\x01\x02")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 3 — __MACOSX/ directory contents filtered (ancestor path check)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_macosx_dir_filtered(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    macosx = folder / "__MACOSX"
    macosx.mkdir()
    # Note: the inner filename itself is NOT a system match; it must be
    # filtered via the ancestor-path check on the `__MACOSX` part.
    (macosx / "file.txt").write_text("should not appear", encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 4 — $RECYCLE.BIN/ directory contents filtered (Windows ancestor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recycle_bin_dir_filtered(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    recycle = folder / "$RECYCLE.BIN"
    recycle.mkdir()
    (recycle / "file.txt").write_text("should not appear", encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 5 — .mov filtered (unsupported extension)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mov_filtered_unsupported_extension(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    (folder / "video.mov").write_bytes(b"\x00\x01\x02fake-mov-bytes")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    # .mov is silently filtered — it must NOT land in `skipped` either
    # (skipped is for whitelisted-extension files the dispatcher rejected).
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 6 — .zip filtered (unsupported extension)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zip_filtered_unsupported_extension(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    (folder / "archive.zip").write_bytes(b"PK\x03\x04fake-zip")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 7 — ._* AppleDouble pattern filtered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apple_double_filtered_pattern(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    # `._image.png` — name starts with `.` so `_is_hidden` ALSO catches
    # it; we want to assert the pattern check independently, so we also
    # add `._notes.md` which would otherwise be claimed by TextHandler
    # if we ever stopped dotfile-filtering.
    (folder / "._image.png").write_bytes(b"\x00\x01\x02")
    (folder / "._notes.md").write_text("ghost", encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 8 — ~$* Office temp pattern filtered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_office_temp_filtered_pattern(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    # `real-doc.docx`: empty body is fine — the dispatcher's DocxHandler
    # `can_handle` checks suffix only (no content sniff at probe time),
    # so any file with a `.docx` extension will route. The body content
    # only matters at extract time, which the plan phase does NOT call.
    (folder / "real-doc.docx").write_bytes(b"PK\x03\x04")
    (folder / "~$document.docx").write_bytes(b"PK\x03\x04")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real-doc.docx"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 9 — .Trash-* Linux trash pattern filtered (belt-and-suspenders
# w/ existing dotfile check, but we assert the system-file path independently)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linux_trash_filtered_pattern(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    trash = folder / ".Trash-1000"
    trash.mkdir()
    (trash / "file.txt").write_text("should not appear", encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 10 — valid extensions all pass the filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_extensions_pass(ephemeral_vault: Path, tmp_path: Path) -> None:
    """All whitelist-claimed extensions (with a registered Path-based
    handler) must enter the plan: .txt + .pdf + .docx + .pptx.

    NOTE: .pdf / .docx / .pptx are claimed by their dispatchers via a
    pure suffix check at probe time (no content read), so empty/dummy
    bytes are sufficient for the plan-phase walk filter assertion. The
    plan does not extract.
    """
    folder = tmp_path / "vault"
    folder.mkdir()
    (folder / "a.txt").write_text("hello", encoding="utf-8")
    # PDFs are claimed on suffix + existence. Minimal magic header avoids
    # any future content-sniffing regression but is not strictly required
    # today.
    (folder / "b.pdf").write_bytes(b"%PDF-1.4\n%fake")
    (folder / "c.docx").write_bytes(b"PK\x03\x04")
    (folder / "d.pptx").write_bytes(b"PK\x03\x04")

    fake = FakeLLMProvider()
    # Use domain_override to skip classify calls — plan-phase only.
    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(
        folder,
        allowed_domains=("research",),
        domain_override="research",
    )

    names = {item.spec.name for item in plan.items}
    assert names == {"a.txt", "b.pdf", "c.docx", "d.pptx"}
    assert plan.skipped == []
    # No classify calls when domain_override is set.
    assert len(fake.requests) == 0


# ---------------------------------------------------------------------------
# Test 11 — combined filters: hidden + system + unsupported all pruned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_combined_with_hidden_check(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    # Hidden directory (caught by `_is_hidden`).
    git = folder / ".git"
    git.mkdir()
    (git / "foo.txt").write_text("git internal", encoding="utf-8")
    # System file (caught by `_is_system_file`).
    (folder / ".DS_Store").write_bytes(b"\x00\x01\x02")
    # Unsupported extension (caught by `_VALID_EXTENSIONS`).
    (folder / "video.mov").write_bytes(b"\x00\x01\x02")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []


# ---------------------------------------------------------------------------
# Test 12 — __pycache__/ dev artifact filtered (ancestor-path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_python_pycache_filtered(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "vault"
    folder.mkdir()
    _real_text(folder)
    pycache = folder / "__pycache__"
    pycache.mkdir()
    (pycache / "foo.pyc").write_bytes(b"\x00\x01\x02")

    fake = FakeLLMProvider()
    fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert {item.spec.name for item in plan.items} == {"real.txt"}
    assert plan.skipped == []
