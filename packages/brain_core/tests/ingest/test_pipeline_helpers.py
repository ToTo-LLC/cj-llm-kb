"""Tests for IngestPipeline pure helper methods (Task 17A).

This file covers:
  - _slug_for / _choose_slug_source
  - _already_ingested
  - _build_source_note
  - ingest() stub (NotImplementedError)

NOTE: The ingest_stub test will be DELETED in Task 17B when the stub is
replaced by real logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import ExtractedSource, SourceType
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import parse_frontmatter, serialize_with_frontmatter
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pipeline(ephemeral_vault: Path) -> IngestPipeline:
    return IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=FakeLLMProvider(),
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _make_summary(**overrides: object) -> SummarizeOutput:
    defaults: dict[str, object] = {
        "title": "Attention Is All You Need",
        "summary": "A paper introducing the Transformer architecture.",
        "key_points": ["Self-attention replaces recurrence.", "Linear position encodings."],
        "entities": ["Vaswani", "Google Brain"],
        "concepts": ["self-attention", "positional encoding"],
        "open_questions": ["How does this scale to longer contexts?"],
    }
    defaults.update(overrides)
    return SummarizeOutput(**defaults)  # type: ignore[arg-type]


def _make_extracted(**overrides: object) -> ExtractedSource:
    defaults: dict[str, object] = {
        "title": "Attention Is All You Need",
        "author": None,
        "published": None,
        "source_url": "https://arxiv.org/abs/1706.03762",
        "source_type": SourceType.URL,
        "body_text": "(full body)",
        "archive_path": Path("/tmp/archive.html"),
    }
    defaults.update(overrides)
    return ExtractedSource(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: _slug_for
# ---------------------------------------------------------------------------


class TestSlugFor:
    def test_path_input_no_title(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for(Path("/x/hello.txt")) == "hello"

    def test_path_input_title_override(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert (
            p._slug_for(Path("/x/hello.txt"), title="Attention Is All You Need")
            == "attention-is-all-you-need"
        )

    def test_url_input(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for("https://example.com/articles/how-llms-work/") == "how-llms-work"

    def test_url_input_no_path(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for("https://example.com") == "example-com"

    def test_plain_text_string(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for("Short first line\n\nLonger body here.") == "short-first-line"

    def test_empty_whitespace_fallback(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for("   ") == "source"

    def test_hard_cap(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        slug = p._slug_for("a" * 200)
        assert len(slug) <= 80

    def test_title_priority_over_filename(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._slug_for(Path("/x/boring.txt"), title="Exciting Title") == "exciting-title"


# ---------------------------------------------------------------------------
# Tests: _already_ingested
# ---------------------------------------------------------------------------


class TestAlreadyIngested:
    def test_empty_vault_returns_false(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        assert p._already_ingested("abc123", ("research", "work")) is False

    def test_match_in_domain(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        note_content = serialize_with_frontmatter({"content_hash": "abc123"}, body="body\n")
        (ephemeral_vault / "research" / "sources" / "x.md").write_text(
            note_content, encoding="utf-8"
        )
        assert p._already_ingested("abc123", ("research",)) is True

    def test_match_in_non_searched_domain(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        note_content = serialize_with_frontmatter({"content_hash": "abc123"}, body="body\n")
        (ephemeral_vault / "research" / "sources" / "x.md").write_text(
            note_content, encoding="utf-8"
        )
        # Only search work — match is in research
        assert p._already_ingested("abc123", ("work",)) is False

    def test_malformed_frontmatter_skipped(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        (ephemeral_vault / "research" / "sources" / "bad.md").write_text(
            "garbage content with no frontmatter fences", encoding="utf-8"
        )
        # Should not crash, and the garbage file is not a match
        assert p._already_ingested("abc123", ("research",)) is False

    def test_missing_sources_dir(self, ephemeral_vault: Path) -> None:
        p = _pipeline(ephemeral_vault)
        # Remove personal/sources
        personal_sources = ephemeral_vault / "personal" / "sources"
        import shutil

        shutil.rmtree(personal_sources)
        # Should not crash
        assert p._already_ingested("abc123", ("personal",)) is False


# ---------------------------------------------------------------------------
# Tests: _build_source_note
# ---------------------------------------------------------------------------


class TestBuildSourceNote:
    _NOW = datetime(2026, 4, 14, 9, 30, tzinfo=UTC)
    _SLUG = "attention-is-all-you-need"
    _CHASH = "deadbeef"
    _DOMAIN = "research"

    def _build(self, ephemeral_vault: Path, **kw: object) -> tuple[Path, str]:
        p = _pipeline(ephemeral_vault)
        summary = kw.pop("summary", _make_summary())
        extracted = kw.pop("extracted", _make_extracted())
        return p._build_source_note(
            extracted=extracted,  # type: ignore[arg-type]
            summary=summary,  # type: ignore[arg-type]
            domain=self._DOMAIN,
            chash=self._CHASH,
            now=self._NOW,
            slug=self._SLUG,
            **kw,
        )

    def test_path_structure(self, ephemeral_vault: Path) -> None:
        note_path, _ = self._build(ephemeral_vault)
        expected = ephemeral_vault / "research" / "sources" / "attention-is-all-you-need.md"
        assert note_path == expected

    def test_frontmatter_fields_present(self, ephemeral_vault: Path) -> None:
        _, content = self._build(ephemeral_vault)
        fm, _ = parse_frontmatter(content)
        assert fm["title"] == "Attention Is All You Need"
        assert fm["domain"] == "research"
        assert fm["type"] == "source"
        assert fm["created"] == "2026-04-14"
        assert fm["updated"] == "2026-04-14"
        assert fm["source_type"] == "url"
        assert fm["source_url"] == "https://arxiv.org/abs/1706.03762"
        assert fm["content_hash"] == "deadbeef"
        assert fm["ingested_by"] == "brain"

    def test_created_updated_dates(self, ephemeral_vault: Path) -> None:
        _, content = self._build(ephemeral_vault)
        fm, _ = parse_frontmatter(content)
        assert fm["created"] == "2026-04-14"
        assert fm["updated"] == "2026-04-14"

    def test_body_contains_sections(self, ephemeral_vault: Path) -> None:
        _, content = self._build(ephemeral_vault)
        _, body = parse_frontmatter(content)
        assert "# Attention Is All You Need" in body
        assert "## Key points" in body
        assert "Self-attention replaces recurrence." in body
        assert "## Entities" in body
        assert "Vaswani" in body
        assert "## Concepts" in body
        assert "self-attention" in body
        assert "## Open questions" in body
        assert "How does this scale to longer contexts?" in body

    def test_empty_list_rendering(self, ephemeral_vault: Path) -> None:
        summary = _make_summary(entities=[], concepts=[], open_questions=[])
        _, content = self._build(ephemeral_vault, summary=summary)
        _, body = parse_frontmatter(content)
        assert "_(none)_" in body

    def test_url_less_source_no_crash(self, ephemeral_vault: Path) -> None:
        extracted = _make_extracted(source_url=None)
        _note_path, content = self._build(ephemeral_vault, extracted=extracted)
        # Must not crash; frontmatter source_url should be None/null
        fm, _ = parse_frontmatter(content)
        assert fm.get("source_url") is None


# ---------------------------------------------------------------------------
# Test: ingest() stub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_stub_raises_not_implemented(ephemeral_vault: Path) -> None:
    # NOTE: Delete this test in Task 17B when the stub is replaced by real logic.
    p = _pipeline(ephemeral_vault)
    with pytest.raises(NotImplementedError):
        await p.ingest(Path("x.txt"), allowed_domains=("research",))
