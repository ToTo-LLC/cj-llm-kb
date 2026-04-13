# Plan 02 — Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full ingestion pipeline in `brain_core.ingest` — per-type source handlers (text, url, pdf, email, transcript in `.txt`/`.vtt`/`.srt`/`.docx`, tweet), an LLM-backed summarize / integrate / classify prompt layer, idempotent content-hashed pipeline orchestration, bulk import with dry-run, and a working demo script that ingests real-ish fixtures end-to-end via `FakeLLMProvider`.

**Architecture:** Plan 02 sits strictly on top of Plan 01's `brain_core`. It adds `brain_core.ingest` (the pipeline) and `brain_core.prompts` (the LLM prompt layer), both of which depend on but never modify the Plan 01 modules. The pipeline drives writes through `VaultWriter.apply()` — no new code may write to the vault outside that abstraction. All LLM calls go through `brain_core.llm.LLMProvider`; tests use `FakeLLMProvider` with pre-recorded responses, so Plan 02 is fully executable with no real network access and no Anthropic API key. Real-API **VCR contract tests** are a parallel track (Tasks 20–22) that can be recorded whenever a key is available; they are not a merge gate.

**Tech Stack:** Python 3.12 · pydantic v2 · `httpx` + `respx` (URL + tweet handlers, with HTTP mocking) · `trafilatura` (HTML → text) · `pymupdf` (PDF text extraction) · `webvtt-py` (VTT/SRT parsing) · `python-docx` (docx transcript parsing) · `vcrpy` + `pytest-vcr` (cassette-based contract tests) · `pytest`, `mypy --strict`, `ruff` (same gates as Plan 01).

**Demo gate:** `uv run python scripts/demo-plan-02.py` ingests five fixtures (a text blob, a mocked URL fetch, a small PDF fixture, a `.vtt` transcript fixture, a mocked tweet) into a temp vault via the full pipeline using `FakeLLMProvider` with pre-queued summarize/integrate/classify responses. The script asserts: (1) five wiki notes were written via `VaultWriter` with correct frontmatter including `content_hash`, (2) the per-domain `index.md` files gained one entry per source, (3) each domain's `log.md` has the ingest entries, (4) a second run with the same inputs is a **no-op** (idempotency), (5) the cost ledger has one row per LLM call, and prints `PLAN 02 DEMO OK` on exit 0.

**Owning subagents:** `brain-core-engineer` (pipeline + handlers + archive + bulk), `brain-prompt-engineer` (prompt files + schemas + contract tests), `brain-test-engineer` (VCR infra + coverage sweep).

**Pre-flight** (main loop, before dispatching Task 1):
- Verify `tasks/lessons.md` is up to date from Plan 01.
- Confirm no uncommitted changes on `main`.
- Confirm `plan-01-foundation` tag exists (`git tag --list | grep plan-01`).
- Optional: note whether `ANTHROPIC_API_KEY` is available in the environment so the cassette-recording track (Tasks 21) can run; if not, that track stays skipped and is revisited later.

---

## File structure produced by this plan

```
packages/brain_core/
├── pyproject.toml                # new deps added: httpx, trafilatura, pymupdf, webvtt-py, python-docx, respx, vcrpy, pytest-vcr + types-*
├── src/brain_core/
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── types.py              # ExtractedSource, SourceType, IngestResult, IngestStatus
│   │   ├── hashing.py            # content_hash helpers
│   │   ├── dispatcher.py         # rule-based type detection + handler registry
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # SourceHandler Protocol + ABC + HandlerError
│   │   │   ├── text.py
│   │   │   ├── url.py
│   │   │   ├── pdf.py
│   │   │   ├── email.py
│   │   │   ├── transcript_text.py
│   │   │   ├── transcript_vtt.py
│   │   │   ├── transcript_docx.py
│   │   │   └── tweet.py
│   │   ├── classifier.py         # LLM-backed domain classifier with confidence
│   │   ├── archive.py            # raw/archive/<domain>/<yyyy>/<mm>/<slug>.<ext>
│   │   ├── failures.py           # raw/inbox/failed/<slug>.error.json
│   │   ├── pipeline.py           # 9-stage orchestrator
│   │   └── bulk.py               # recursive folder walk + dry-run + apply
│   └── prompts/
│       ├── __init__.py
│       ├── loader.py             # .md prompt file loader + variable substitution
│       ├── schemas.py            # pydantic output schemas for each prompt
│       ├── summarize.md
│       ├── integrate.md
│       └── classify.md
└── tests/
    ├── ingest/
    │   ├── __init__.py
    │   ├── conftest.py           # ingest fixtures: sample pdf, vtt, docx, email text
    │   ├── fixtures/
    │   │   ├── hello.txt
    │   │   ├── sample.pdf        # smallest legal PDF, text-extractable
    │   │   ├── meeting.vtt
    │   │   ├── meeting.srt
    │   │   ├── notes.docx
    │   │   ├── email.txt
    │   │   └── tweet.json        # canned syndication.twimg.com response
    │   ├── test_types.py
    │   ├── test_hashing.py
    │   ├── test_dispatcher.py
    │   ├── test_handler_text.py
    │   ├── test_handler_url.py
    │   ├── test_handler_pdf.py
    │   ├── test_handler_email.py
    │   ├── test_handler_transcript_text.py
    │   ├── test_handler_transcript_vtt.py
    │   ├── test_handler_transcript_docx.py
    │   ├── test_handler_tweet.py
    │   ├── test_classifier.py
    │   ├── test_archive.py
    │   ├── test_failures.py
    │   ├── test_pipeline.py
    │   ├── test_bulk.py
    │   └── test_idempotency.py
    └── prompts/
        ├── __init__.py
        ├── test_loader.py
        ├── test_summarize.py
        ├── test_integrate.py
        ├── test_classify.py
        └── cassettes/            # VCR cassettes (optional, recorded if API key available)
            └── .gitkeep
scripts/
├── demo-plan-02.py
└── fixtures/
    └── (same tree as tests/ingest/fixtures/ for demo consumption)
```

---

## Per-task self-review checklist (runs in every TDD task)

Every implementer task MUST end with this checklist before reporting DONE. This is a new discipline vs. Plan 01 — the "run ruff per task" lesson from Task 21 is now a hard requirement.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core`
3. `uv run pytest packages/brain_core -q` — all tests pass, no regressions
4. `cd packages/brain_core && uv run mypy src tests && cd ../..` — strict clean
5. `uv run ruff check .` — clean
6. `uv run ruff format --check .` — clean
7. `git status` — clean after commit

Any failure in 3–6 must be fixed before reporting DONE. No blanket ignores, no weakened assertions, no coverage-threshold lowering.

---

## Task 1 — Ingest deps, package skeleton, `ingest.types`, `SourceHandler` Protocol

**Files:**
- Modify: `packages/brain_core/pyproject.toml` (deps)
- Modify: `pyproject.toml` (root — add types-* dev deps)
- Create: `packages/brain_core/src/brain_core/ingest/__init__.py`
- Create: `packages/brain_core/src/brain_core/ingest/types.py`
- Create: `packages/brain_core/src/brain_core/ingest/handlers/__init__.py`
- Create: `packages/brain_core/src/brain_core/ingest/handlers/base.py`
- Create: `packages/brain_core/tests/ingest/__init__.py`
- Create: `packages/brain_core/tests/ingest/test_types.py`

- [ ] **Step 1.1: Add runtime deps to `packages/brain_core/pyproject.toml`**

Edit the existing `dependencies = [...]` list to include:
```toml
dependencies = [
    "pydantic>=2.8",
    "pyyaml>=6.0",
    "structlog>=24.4",
    "filelock>=3.15",
    "anthropic>=0.40",
    # Plan 02 — ingest pipeline
    "httpx>=0.27",
    "trafilatura>=1.12",
    "pymupdf>=1.24",
    "webvtt-py>=0.5",
    "python-docx>=1.1",
]
```

- [ ] **Step 1.2: Add test/dev deps to the root `pyproject.toml`**

Under `[dependency-groups].dev`, append:
```toml
    "respx>=0.21",          # httpx mocking for handler tests
    "vcrpy>=6.0",           # cassette-based contract tests
    "pytest-vcr>=1.0",
    "types-PyYAML>=6.0",    # already present from Plan 01, leave as-is
```

- [ ] **Step 1.3: `uv sync` and verify**

```
export PATH="$HOME/.local/bin:$PATH"
uv sync
```
Expected: all new packages install cleanly. Exit 0.

- [ ] **Step 1.4: Write the failing type test**

Create `packages/brain_core/tests/ingest/__init__.py` (empty).

Create `packages/brain_core/tests/ingest/test_types.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from brain_core.ingest.types import (
    ExtractedSource,
    IngestResult,
    IngestStatus,
    SourceType,
)


def test_extracted_source_round_trip() -> None:
    es = ExtractedSource(
        title="A Title",
        author="An Author",
        published=date(2026, 4, 13),
        source_url="https://example.com/a",
        source_type=SourceType.URL,
        body_text="Hello body.",
        archive_path=Path("/tmp/archive/a.html"),
        extras={"hash": "abc"},
    )
    assert es.title == "A Title"
    assert es.source_type is SourceType.URL
    assert es.extras["hash"] == "abc"


def test_ingest_result_defaults() -> None:
    r = IngestResult(status=IngestStatus.OK, note_path=None)
    assert r.status is IngestStatus.OK
    assert r.note_path is None
    assert r.errors == []


def test_source_type_is_str_enum() -> None:
    assert SourceType.URL.value == "url"
    assert str(SourceType.PDF) == "SourceType.PDF"
```

- [ ] **Step 1.5: Run, verify failure**

```
uv run pytest packages/brain_core/tests/ingest/test_types.py -v
```
Expected: `ModuleNotFoundError: No module named 'brain_core.ingest'`.

- [ ] **Step 1.6: Implement `ingest/__init__.py`**

```python
"""brain_core.ingest — source pipeline: classify → fetch → extract → archive → route → summarize → integrate → apply → log."""
```

- [ ] **Step 1.7: Implement `ingest/types.py`**

```python
"""Typed models shared across the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any


class SourceType(str, Enum):
    TEXT = "text"
    URL = "url"
    PDF = "pdf"
    EMAIL = "email"
    TRANSCRIPT = "transcript"
    TWEET = "tweet"


class IngestStatus(str, Enum):
    OK = "ok"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"


@dataclass(frozen=True)
class ExtractedSource:
    title: str | None
    author: str | None
    published: date | None
    source_url: str | None
    source_type: SourceType
    body_text: str
    archive_path: Path
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    status: IngestStatus
    note_path: Path | None
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    extracted: ExtractedSource | None = None
```

- [ ] **Step 1.8: Implement `ingest/handlers/__init__.py`**

```python
"""brain_core.ingest.handlers — per-source-type fetch+extract implementations."""
```

- [ ] **Step 1.9: Implement `ingest/handlers/base.py`**

```python
"""SourceHandler Protocol and the handler registry."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from brain_core.ingest.types import ExtractedSource, SourceType


class HandlerError(RuntimeError):
    """Raised when a handler cannot fetch or extract a source."""


@runtime_checkable
class SourceHandler(Protocol):
    """Contract every per-type handler satisfies."""

    source_type: SourceType

    async def can_handle(self, spec: str | Path) -> bool: ...

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource: ...


# Populated at import time by each handler module via register().
HANDLERS: list[SourceHandler] = []


def register(handler: SourceHandler) -> None:
    HANDLERS.append(handler)
```

- [ ] **Step 1.10: Reinstall, run tests, mypy, ruff**

```
uv sync --reinstall-package brain_core
uv run pytest packages/brain_core -q
cd packages/brain_core && uv run mypy src tests && cd ../..
uv run ruff check .
uv run ruff format --check .
```

Expected: 67 passed (64 prior + 3 new), mypy clean, ruff clean.

- [ ] **Step 1.11: Commit**

```bash
git add packages/brain_core pyproject.toml uv.lock
git commit -m "feat(brain_core): ingest types, SourceHandler Protocol, Plan 02 deps"
```

---

## Task 2 — Content hashing helper

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/hashing.py`
- Create: `packages/brain_core/tests/ingest/test_hashing.py`

- [ ] **Step 2.1: Write failing test**

```python
# packages/brain_core/tests/ingest/test_hashing.py
from __future__ import annotations

from brain_core.ingest.hashing import content_hash


def test_stable_hash_same_bytes() -> None:
    assert content_hash("hello") == content_hash("hello")


def test_different_input_different_hash() -> None:
    assert content_hash("a") != content_hash("b")


def test_handles_unicode() -> None:
    h = content_hash("hello — world ✓")
    assert len(h) == 64  # sha256 hex
    assert all(c in "0123456789abcdef" for c in h)


def test_bytes_input_matches_string_input() -> None:
    assert content_hash("hello") == content_hash(b"hello")
```

- [ ] **Step 2.2: Run, verify failure.**

- [ ] **Step 2.3: Implement `ingest/hashing.py`**

```python
"""Content hashing for idempotent ingest."""

from __future__ import annotations

import hashlib


def content_hash(data: str | bytes) -> str:
    """Return a stable SHA-256 hex digest of the input content."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
```

- [ ] **Step 2.4: Run tests + full gates per checklist. Expect 71 passed.**

- [ ] **Step 2.5: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/hashing.py packages/brain_core/tests/ingest/test_hashing.py
git commit -m "feat(brain_core): stable content_hash helper for idempotency"
```

---

## Task 3 — Text/Markdown handler

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/text.py`
- Create: `packages/brain_core/tests/ingest/test_handler_text.py`
- Create: `packages/brain_core/tests/ingest/fixtures/hello.txt`
- Create: `packages/brain_core/tests/ingest/conftest.py`

- [ ] **Step 3.1: Create the fixture file**

`packages/brain_core/tests/ingest/fixtures/hello.txt`:
```
Hello, brain.
This is a plain-text fixture for the text handler.
```

- [ ] **Step 3.2: Create `packages/brain_core/tests/ingest/conftest.py`**

```python
"""Shared fixtures for ingest tests."""

from __future__ import annotations

from pathlib import Path

import pytest

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return _FIXTURES
```

- [ ] **Step 3.3: Write failing test**

```python
# packages/brain_core/tests/ingest/test_handler_text.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_text_handler_reads_plain_text_file(tmp_path: Path, fixtures_dir: Path) -> None:
    h = TextHandler()
    assert await h.can_handle(fixtures_dir / "hello.txt")
    extracted = await h.extract(fixtures_dir / "hello.txt", archive_root=tmp_path)
    assert extracted.source_type is SourceType.TEXT
    assert "Hello, brain." in extracted.body_text
    assert extracted.archive_path.exists()
    assert extracted.title == "hello"


@pytest.mark.asyncio
async def test_text_handler_rejects_non_text(tmp_path: Path) -> None:
    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    assert await TextHandler().can_handle(f) is False
```

- [ ] **Step 3.4: Run, verify failure.**

- [ ] **Step 3.5: Implement `ingest/handlers/text.py`**

```python
"""Plain text / Markdown handler. Copies the file into archive and reads UTF-8."""

from __future__ import annotations

import shutil
from pathlib import Path

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType

_EXTS = {".txt", ".md", ".markdown"}


class TextHandler:
    source_type: SourceType = SourceType.TEXT

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, Path):
            return False
        return spec.suffix.lower() in _EXTS and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"text handler cannot read {spec!r}")
        body = spec.read_text(encoding="utf-8")
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.TEXT,
            body_text=body,
            archive_path=archive_path,
        )
```

- [ ] **Step 3.6: Full gates.** Expect 73 passed.

- [ ] **Step 3.7: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/handlers/text.py packages/brain_core/tests/ingest
git commit -m "feat(brain_core): text/markdown source handler"
```

---

## Task 4 — URL handler (httpx + trafilatura, respx-mocked)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/url.py`
- Create: `packages/brain_core/tests/ingest/test_handler_url.py`

- [ ] **Step 4.1: Write failing test**

```python
# packages/brain_core/tests/ingest/test_handler_url.py
from __future__ import annotations

from pathlib import Path

import pytest
import respx
import httpx

from brain_core.ingest.handlers.url import URLHandler
from brain_core.ingest.types import SourceType


_HTML = """
<!doctype html>
<html><head><title>Example article</title></head>
<body>
  <article>
    <h1>Example article</h1>
    <p>This is the main body content that trafilatura should pick up.</p>
    <p>It has two paragraphs to prove multi-paragraph extraction works.</p>
  </article>
  <footer>nav junk</footer>
</body></html>
"""


@pytest.mark.asyncio
async def test_url_handler_fetches_and_extracts(tmp_path: Path) -> None:
    async with respx.mock(base_url="https://example.com") as mock:
        mock.get("/a").mock(return_value=httpx.Response(200, text=_HTML))
        h = URLHandler()
        assert await h.can_handle("https://example.com/a")
        es = await h.extract("https://example.com/a", archive_root=tmp_path)
    assert es.source_type is SourceType.URL
    assert "main body content" in es.body_text
    assert es.title == "Example article"
    assert es.source_url == "https://example.com/a"
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_url_handler_rejects_non_http() -> None:
    h = URLHandler()
    assert await h.can_handle("file:///etc/passwd") is False
    assert await h.can_handle(Path("/tmp/x")) is False
```

- [ ] **Step 4.2: Run, verify failure.**

- [ ] **Step 4.3: Implement `ingest/handlers/url.py`**

```python
"""URL handler — fetches with httpx, extracts readable content with trafilatura."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, SourceType


class URLHandler:
    source_type: SourceType = SourceType.URL

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        parsed = urlparse(spec)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"url handler cannot read {spec!r}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(spec)
            resp.raise_for_status()
            html = resp.text
            final_url = str(resp.url)

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta and meta.title else None
        author = meta.author if meta and meta.author else None

        archive_root.mkdir(parents=True, exist_ok=True)
        h = content_hash(html)[:16]
        archive_path = archive_root / f"{h}.html"
        archive_path.write_text(html, encoding="utf-8")

        return ExtractedSource(
            title=title,
            author=author,
            published=None,
            source_url=final_url,
            source_type=SourceType.URL,
            body_text=extracted,
            archive_path=archive_path,
        )
```

- [ ] **Step 4.4: Full gates.** Expect 75 passed.

- [ ] **Step 4.5: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/handlers/url.py packages/brain_core/tests/ingest/test_handler_url.py
git commit -m "feat(brain_core): URL source handler with trafilatura extraction"
```

**Note**: `trafilatura` currently exposes some Python-3.9-style internals. If mypy strict complains about an untyped `trafilatura` import, add `types-trafilatura` to dev deps if it exists; otherwise add `[[tool.mypy.overrides]] module = "trafilatura" ignore_missing_imports = true` scoped to this one module. Record as a lesson if the latter path is needed.

---

## Task 5 — PDF handler (pymupdf)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/pdf.py`
- Create: `packages/brain_core/tests/ingest/test_handler_pdf.py`
- Create: `packages/brain_core/tests/ingest/fixtures/sample.pdf`

- [ ] **Step 5.1: Generate the smallest-possible text PDF fixture**

Create a one-off Python script (one-liner inline, don't commit) to produce a small text-extractable PDF:

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 100), 'Plan 02 PDF fixture\\nParagraph one.\\nParagraph two.')
doc.save('packages/brain_core/tests/ingest/fixtures/sample.pdf')
doc.close()
"
```

Verify: `ls -la packages/brain_core/tests/ingest/fixtures/sample.pdf` shows a small file (likely under 2 KB).

- [ ] **Step 5.2: Write failing test**

```python
# packages/brain_core/tests/ingest/test_handler_pdf.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.ingest.handlers.pdf import PDFHandler, ScannedPDFError
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_pdf_handler_extracts_text(tmp_path: Path, fixtures_dir: Path) -> None:
    h = PDFHandler()
    assert await h.can_handle(fixtures_dir / "sample.pdf")
    es = await h.extract(fixtures_dir / "sample.pdf", archive_root=tmp_path)
    assert es.source_type is SourceType.PDF
    assert "Plan 02 PDF fixture" in es.body_text
    assert "Paragraph one." in es.body_text
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_pdf_handler_flags_probable_scan(tmp_path: Path) -> None:
    """A PDF whose extracted text is below the min-chars threshold must raise ScannedPDFError."""
    import fitz  # type: ignore[import-untyped]
    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()  # no text
    doc.save(p)
    doc.close()
    with pytest.raises(ScannedPDFError):
        await PDFHandler(min_chars=50).extract(p, archive_root=tmp_path)


@pytest.mark.asyncio
async def test_pdf_handler_rejects_non_pdf(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("not a pdf", encoding="utf-8")
    assert await PDFHandler().can_handle(f) is False
```

- [ ] **Step 5.3: Run, verify failure.**

- [ ] **Step 5.4: Implement `ingest/handlers/pdf.py`**

```python
"""PDF handler — text-only extraction via pymupdf. Scanned PDFs are flagged, not OCR'd."""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType


class ScannedPDFError(HandlerError):
    """Raised when the PDF appears to be a scan (too little extractable text)."""


class PDFHandler:
    source_type: SourceType = SourceType.PDF

    def __init__(self, *, min_chars: int = 200) -> None:
        self._min_chars = min_chars

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, Path):
            return False
        return spec.suffix.lower() == ".pdf" and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"pdf handler cannot read {spec!r}")
        doc = fitz.open(spec)
        try:
            parts: list[str] = []
            title = None
            try:
                meta = doc.metadata or {}
                title = meta.get("title") or None
            except Exception:
                title = None
            for page in doc:
                parts.append(page.get_text())
        finally:
            doc.close()
        body = "\n\n".join(p.strip() for p in parts if p.strip())
        if len(body) < self._min_chars:
            raise ScannedPDFError(
                f"extracted {len(body)} chars from {spec.name}; below min={self._min_chars} (likely scanned)"
            )
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=title or spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.PDF,
            body_text=body,
            archive_path=archive_path,
        )
```

- [ ] **Step 5.5: Full gates.** Expect 78 passed.

- [ ] **Step 5.6: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/handlers/pdf.py packages/brain_core/tests/ingest/test_handler_pdf.py packages/brain_core/tests/ingest/fixtures/sample.pdf
git commit -m "feat(brain_core): PDF source handler (text-only, flags scanned PDFs)"
```

---

## Task 6 — Email handler (pasted text)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/email.py`
- Create: `packages/brain_core/tests/ingest/test_handler_email.py`
- Create: `packages/brain_core/tests/ingest/fixtures/email.txt`

- [ ] **Step 6.1: Create the fixture**

`packages/brain_core/tests/ingest/fixtures/email.txt`:
```
From: Alice <alice@example.com>
To: Bob <bob@example.com>
Subject: Q2 planning
Date: Mon, 13 Apr 2026 09:00:00 -0700

Hey Bob,

Let's sync on Q2 planning this Thursday.

Agenda:
- Budget review
- Hiring pipeline
- Roadmap check-in

Thanks,
Alice
```

- [ ] **Step 6.2: Write failing test**

```python
# packages/brain_core/tests/ingest/test_handler_email.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.ingest.handlers.email import EmailHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_email_handler_parses_header_and_body(fixtures_dir: Path, tmp_path: Path) -> None:
    text = (fixtures_dir / "email.txt").read_text(encoding="utf-8")
    h = EmailHandler()
    assert await h.can_handle(text) is True
    es = await h.extract(text, archive_root=tmp_path)
    assert es.source_type is SourceType.EMAIL
    assert es.title == "Q2 planning"
    assert es.author and "alice@example.com" in es.author
    assert "Budget review" in es.body_text
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_email_handler_rejects_non_email_text() -> None:
    assert await EmailHandler().can_handle("just a random paragraph") is False
```

- [ ] **Step 6.3: Run, verify failure.**

- [ ] **Step 6.4: Implement `ingest/handlers/email.py`**

```python
"""Email handler — pasted .eml-style text. Uses stdlib email.parser."""

from __future__ import annotations

from email import message_from_string
from email.utils import parseaddr
from pathlib import Path

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, SourceType

_REQUIRED_HEADERS = {"from", "to", "subject"}


class EmailHandler:
    source_type: SourceType = SourceType.EMAIL

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        head = spec.splitlines()[:10]
        seen = {
            line.split(":", 1)[0].strip().lower()
            for line in head
            if ":" in line
        }
        return _REQUIRED_HEADERS.issubset(seen)

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"email handler cannot read {spec!r}")
        msg = message_from_string(spec)
        subject = msg.get("Subject", "").strip() or None
        from_raw = msg.get("From", "")
        _, from_addr = parseaddr(from_raw)
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body_text += payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body_text = payload.decode("utf-8", errors="replace")
            else:
                body_text = msg.get_payload(decode=False) or ""
        if not body_text:
            # plain-text paste: parser puts it all under payload, which we already read.
            body_text = spec.split("\n\n", 1)[-1] if "\n\n" in spec else spec

        archive_root.mkdir(parents=True, exist_ok=True)
        h = content_hash(spec)[:16]
        archive_path = archive_root / f"{h}.eml"
        archive_path.write_text(spec, encoding="utf-8")

        return ExtractedSource(
            title=subject,
            author=from_addr or None,
            published=None,
            source_url=None,
            source_type=SourceType.EMAIL,
            body_text=body_text.strip(),
            archive_path=archive_path,
        )
```

- [ ] **Step 6.5: Full gates.** Expect 80 passed.

- [ ] **Step 6.6: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/handlers/email.py packages/brain_core/tests/ingest/test_handler_email.py packages/brain_core/tests/ingest/fixtures/email.txt
git commit -m "feat(brain_core): email handler for pasted .eml-style text"
```

---

## Tasks 7–9 — Transcript handlers (txt, vtt/srt, docx)

Each follows the same TDD pattern: fixture → failing test → impl → gates → commit. Code is shown; steps are collapsed for brevity but still atomic.

### Task 7 — Transcript TEXT handler

- [ ] **Step 7.1**: Create fixture `packages/brain_core/tests/ingest/fixtures/transcript.txt`:
  ```
  Alice: Welcome to the meeting.
  Bob: Thanks for setting this up.
  Alice: Let's start with the roadmap.
  ```
- [ ] **Step 7.2**: Write failing test `test_handler_transcript_text.py`:
  ```python
  from __future__ import annotations
  from pathlib import Path
  import pytest
  from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
  from brain_core.ingest.types import SourceType

  @pytest.mark.asyncio
  async def test_plain_transcript(fixtures_dir: Path, tmp_path: Path) -> None:
      h = TranscriptTextHandler()
      es = await h.extract(fixtures_dir / "transcript.txt", archive_root=tmp_path)
      assert es.source_type is SourceType.TRANSCRIPT
      assert "Alice" in es.body_text
  ```
- [ ] **Step 7.3**: Implement `packages/brain_core/src/brain_core/ingest/handlers/transcript_text.py`:
  ```python
  """Plain-text transcript handler. Reuses the plain-text read path, tags as TRANSCRIPT."""

  from __future__ import annotations

  import shutil
  from pathlib import Path

  from brain_core.ingest.handlers.base import HandlerError
  from brain_core.ingest.types import ExtractedSource, SourceType

  _EXTS = {".txt"}


  class TranscriptTextHandler:
      source_type: SourceType = SourceType.TRANSCRIPT

      async def can_handle(self, spec: str | Path) -> bool:
          if not isinstance(spec, Path):
              return False
          return spec.suffix.lower() in _EXTS and spec.exists() and "transcript" in spec.stem.lower()

      async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
          if not isinstance(spec, Path) or not spec.exists():
              raise HandlerError(f"transcript_text cannot read {spec!r}")
          body = spec.read_text(encoding="utf-8")
          archive_root.mkdir(parents=True, exist_ok=True)
          archive_path = archive_root / spec.name
          shutil.copy2(spec, archive_path)
          return ExtractedSource(
              title=spec.stem,
              author=None,
              published=None,
              source_url=None,
              source_type=SourceType.TRANSCRIPT,
              body_text=body,
              archive_path=archive_path,
          )
  ```
- [ ] **Step 7.4**: Run gates. Expect 81 passed.
- [ ] **Step 7.5**: Commit: `git commit -m "feat(brain_core): plain-text transcript handler"`.

### Task 8 — Transcript VTT/SRT handler

- [ ] **Step 8.1**: Create fixture `packages/brain_core/tests/ingest/fixtures/meeting.vtt`:
  ```
  WEBVTT

  00:00:00.000 --> 00:00:03.000
  Alice: Welcome to the meeting.

  00:00:03.000 --> 00:00:06.000
  Bob: Thanks for setting this up.

  00:00:06.000 --> 00:00:10.000
  Alice: Let's start with the roadmap.
  ```
  And `meeting.srt`:
  ```
  1
  00:00:00,000 --> 00:00:03,000
  Alice: Welcome to the meeting.

  2
  00:00:03,000 --> 00:00:06,000
  Bob: Thanks for setting this up.
  ```
- [ ] **Step 8.2**: Failing test `test_handler_transcript_vtt.py` (exercises both VTT and SRT paths, asserts timestamps are stripped and speakers preserved).
- [ ] **Step 8.3**: Implement `handlers/transcript_vtt.py` using `webvtt`:
  ```python
  """VTT/SRT transcript handler — strips timestamps, preserves speakers."""

  from __future__ import annotations

  import shutil
  from pathlib import Path

  import webvtt

  from brain_core.ingest.handlers.base import HandlerError
  from brain_core.ingest.types import ExtractedSource, SourceType

  _EXTS = {".vtt", ".srt"}


  class TranscriptVTTHandler:
      source_type: SourceType = SourceType.TRANSCRIPT

      async def can_handle(self, spec: str | Path) -> bool:
          return isinstance(spec, Path) and spec.suffix.lower() in _EXTS and spec.exists()

      async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
          if not isinstance(spec, Path) or not spec.exists():
              raise HandlerError(f"transcript_vtt cannot read {spec!r}")
          if spec.suffix.lower() == ".srt":
              captions = webvtt.from_srt(str(spec))
          else:
              captions = webvtt.read(str(spec))
          lines = [c.text.strip() for c in captions if c.text.strip()]
          body = "\n".join(lines)
          archive_root.mkdir(parents=True, exist_ok=True)
          archive_path = archive_root / spec.name
          shutil.copy2(spec, archive_path)
          return ExtractedSource(
              title=spec.stem,
              author=None,
              published=None,
              source_url=None,
              source_type=SourceType.TRANSCRIPT,
              body_text=body,
              archive_path=archive_path,
          )
  ```
- [ ] **Step 8.4**: Gates. Expect 83 passed (2 new).
- [ ] **Step 8.5**: Commit: `feat(brain_core): vtt/srt transcript handler`.

### Task 9 — Transcript DOCX handler

- [ ] **Step 9.1**: Create fixture generator and run it once to produce `fixtures/notes.docx`:
  ```
  uv run python -c "
  from docx import Document
  d = Document()
  d.add_paragraph('Meeting notes 2026-04-13')
  d.add_paragraph('Alice: Welcome to the meeting.')
  d.add_paragraph('Bob: Thanks for setting this up.')
  d.save('packages/brain_core/tests/ingest/fixtures/notes.docx')
  "
  ```
- [ ] **Step 9.2**: Failing test `test_handler_transcript_docx.py` asserting body contains all three paragraph strings.
- [ ] **Step 9.3**: Implement `handlers/transcript_docx.py`:
  ```python
  """DOCX transcript handler — reads paragraphs with python-docx."""

  from __future__ import annotations

  import shutil
  from pathlib import Path

  from docx import Document  # type: ignore[import-untyped]

  from brain_core.ingest.handlers.base import HandlerError
  from brain_core.ingest.types import ExtractedSource, SourceType


  class TranscriptDOCXHandler:
      source_type: SourceType = SourceType.TRANSCRIPT

      async def can_handle(self, spec: str | Path) -> bool:
          return isinstance(spec, Path) and spec.suffix.lower() == ".docx" and spec.exists()

      async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
          if not isinstance(spec, Path) or not spec.exists():
              raise HandlerError(f"transcript_docx cannot read {spec!r}")
          doc = Document(str(spec))
          body = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
          archive_root.mkdir(parents=True, exist_ok=True)
          archive_path = archive_root / spec.name
          shutil.copy2(spec, archive_path)
          return ExtractedSource(
              title=spec.stem,
              author=None,
              published=None,
              source_url=None,
              source_type=SourceType.TRANSCRIPT,
              body_text=body,
              archive_path=archive_path,
          )
  ```
- [ ] **Step 9.4**: Gates. Expect 84 passed.
- [ ] **Step 9.5**: Commit: `feat(brain_core): docx transcript handler`.

---

## Task 10 — Tweet handler (respx-mocked syndication endpoint)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/tweet.py`
- Create: `packages/brain_core/tests/ingest/test_handler_tweet.py`
- Create: `packages/brain_core/tests/ingest/fixtures/tweet.json` (sample syndication response)

- [ ] **Step 10.1: Create the canned JSON fixture**

`fixtures/tweet.json`:
```json
{
  "id_str": "2039805659525644595",
  "user": {"name": "Andrej Karpathy", "screen_name": "karpathy"},
  "text": "Use LLMs to compile raw info into living markdown wikis.",
  "created_at": "Thu Apr 03 10:00:00 +0000 2026"
}
```

- [ ] **Step 10.2: Failing test**

```python
# packages/brain_core/tests/ingest/test_handler_tweet.py
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_tweet_handler_fetches_and_extracts(fixtures_dir: Path, tmp_path: Path) -> None:
    payload = json.loads((fixtures_dir / "tweet.json").read_text(encoding="utf-8"))
    async with respx.mock(base_url="https://cdn.syndication.twimg.com") as mock:
        mock.get("/tweet-result").mock(return_value=httpx.Response(200, json=payload))
        h = TweetHandler()
        url = "https://x.com/karpathy/status/2039805659525644595"
        assert await h.can_handle(url)
        es = await h.extract(url, archive_root=tmp_path)
    assert es.source_type is SourceType.TWEET
    assert "markdown wikis" in es.body_text
    assert es.author == "karpathy"
    assert es.title and "karpathy" in es.title


@pytest.mark.asyncio
async def test_tweet_handler_rejects_non_tweet_url() -> None:
    h = TweetHandler()
    assert await h.can_handle("https://example.com") is False
    assert await h.can_handle("https://twitter.com/karpathy") is False  # no status ID
```

- [ ] **Step 10.3: Implement `handlers/tweet.py`**

```python
"""Tweet handler — fetches via cdn.syndication.twimg.com (fragile, unauth)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType

_ID_RE = re.compile(r"/status/(\d+)")
_SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result"


class TweetHandler:
    """Fragile unauth handler for single X/Twitter posts."""

    source_type: SourceType = SourceType.TWEET
    fragile: bool = True

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        parsed = urlparse(spec)
        if parsed.netloc not in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}:
            return False
        return bool(_ID_RE.search(parsed.path))

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"tweet handler cannot read {spec!r}")
        m = _ID_RE.search(urlparse(spec).path)
        if not m:
            raise HandlerError(f"no tweet id in {spec}")
        tweet_id = m.group(1)
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(_SYNDICATION, params={"id": tweet_id})
            resp.raise_for_status()
            data = resp.json()
        author = data.get("user", {}).get("screen_name") or None
        display = data.get("user", {}).get("name") or author
        text = data.get("text") or ""
        title = f"Tweet by {display}" if display else f"Tweet {tweet_id}"

        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / f"tweet-{tweet_id}.json"
        archive_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ExtractedSource(
            title=title,
            author=author,
            published=None,
            source_url=spec,
            source_type=SourceType.TWEET,
            body_text=text,
            archive_path=archive_path,
        )
```

- [ ] **Step 10.4: Gates.** Expect 86 passed.

- [ ] **Step 10.5: Commit**

```bash
git add packages/brain_core/src/brain_core/ingest/handlers/tweet.py packages/brain_core/tests/ingest/test_handler_tweet.py packages/brain_core/tests/ingest/fixtures/tweet.json
git commit -m "feat(brain_core): tweet handler via syndication endpoint (fragile)"
```

---

## Task 11 — Dispatcher (rule-based type detection)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/dispatcher.py`
- Create: `packages/brain_core/tests/ingest/test_dispatcher.py`

- [ ] **Step 11.1: Failing test**

```python
# packages/brain_core/tests/ingest/test_dispatcher.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.ingest.dispatcher import dispatch, DispatchError
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler


@pytest.mark.asyncio
async def test_dispatch_url_picks_url_handler() -> None:
    h = await dispatch("https://example.com/a")
    assert isinstance(h, URLHandler)


@pytest.mark.asyncio
async def test_dispatch_tweet_url_picks_tweet_handler_before_url_handler() -> None:
    h = await dispatch("https://x.com/karpathy/status/123")
    assert isinstance(h, TweetHandler)


@pytest.mark.asyncio
async def test_dispatch_pdf_path(fixtures_dir: Path) -> None:
    h = await dispatch(fixtures_dir / "sample.pdf")
    assert isinstance(h, PDFHandler)


@pytest.mark.asyncio
async def test_dispatch_text_path(fixtures_dir: Path) -> None:
    h = await dispatch(fixtures_dir / "hello.txt")
    assert isinstance(h, TextHandler)


@pytest.mark.asyncio
async def test_dispatch_unknown_raises() -> None:
    with pytest.raises(DispatchError):
        await dispatch(Path("/nope/nope.xyz"))
```

- [ ] **Step 11.2: Implement `dispatcher.py`**

```python
"""Source type dispatcher — picks the right handler for a given spec."""

from __future__ import annotations

from pathlib import Path

from brain_core.ingest.handlers.base import SourceHandler
from brain_core.ingest.handlers.email import EmailHandler
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.handlers.transcript_docx import TranscriptDOCXHandler
from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
from brain_core.ingest.handlers.transcript_vtt import TranscriptVTTHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler


class DispatchError(RuntimeError):
    """No handler could claim the given source spec."""


# Order matters: more specific handlers must come first.
# Tweet handler must beat the generic URL handler. Transcript handlers must beat plain text
# for files with a "transcript" in the stem or with a .vtt/.srt/.docx extension.
def _default_handlers() -> list[SourceHandler]:
    return [
        TweetHandler(),
        URLHandler(),
        TranscriptVTTHandler(),
        TranscriptDOCXHandler(),
        TranscriptTextHandler(),
        PDFHandler(),
        EmailHandler(),
        TextHandler(),
    ]


async def dispatch(
    spec: str | Path,
    *,
    handlers: list[SourceHandler] | None = None,
) -> SourceHandler:
    candidates = handlers or _default_handlers()
    for h in candidates:
        if await h.can_handle(spec):
            return h
    raise DispatchError(f"no handler claimed {spec!r}")
```

- [ ] **Step 11.3: Gates.** Expect 91 passed.

- [ ] **Step 11.4: Commit**: `feat(brain_core): ingest dispatcher with deterministic handler ordering`.

---

## Task 12 — Archive + Failures (disk layout)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/archive.py`
- Create: `packages/brain_core/src/brain_core/ingest/failures.py`
- Create: `packages/brain_core/tests/ingest/test_archive.py`
- Create: `packages/brain_core/tests/ingest/test_failures.py`

- [ ] **Step 12.1**: Failing tests for `archive_path_for(vault_root, domain, source_type, slug, now)` → produces `raw/archive/<domain>/<yyyy>/<mm>/<slug>.<ext>` per the spec §4; and for `record_failure(vault_root, slug, stage, exc)` → writes `raw/inbox/failed/<slug>.error.json` with `{"stage": ..., "exception_class": ..., "message": ..., "ts": ...}`.

- [ ] **Step 12.2: Implement `archive.py`**

```python
"""Archive path computation for the raw/archive/ tree."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def archive_dir_for(
    *,
    vault_root: Path,
    domain: str,
    when: datetime,
) -> Path:
    return vault_root / "raw" / "archive" / domain / f"{when.year:04d}" / f"{when.month:02d}"
```

- [ ] **Step 12.3: Implement `failures.py`**

```python
"""Per-source failure records written to raw/inbox/failed/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def record_failure(
    *,
    vault_root: Path,
    slug: str,
    stage: str,
    exception: BaseException,
) -> Path:
    failed_dir = vault_root / "raw" / "inbox" / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    path = failed_dir / f"{slug}.error.json"
    path.write_text(
        json.dumps(
            {
                "slug": slug,
                "stage": stage,
                "exception_class": type(exception).__name__,
                "message": str(exception),
                "ts_utc": datetime.now(tz=UTC).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 12.4: Gates.** Expect 94 passed.

- [ ] **Step 12.5: Commit**: `feat(brain_core): ingest archive path computation + failure records`.

---

## Task 13 — Prompts package + loader + BRAIN.md template

**Files:**
- Create: `packages/brain_core/src/brain_core/prompts/__init__.py`
- Create: `packages/brain_core/src/brain_core/prompts/loader.py`
- Create: `packages/brain_core/src/brain_core/prompts/schemas.py`
- Create: `docs/BRAIN.md.template`
- Create: `packages/brain_core/tests/prompts/__init__.py`
- Create: `packages/brain_core/tests/prompts/test_loader.py`

- [ ] **Step 13.1**: Failing test for `load_prompt(name)` returning a `Prompt` dataclass with `system`, `user_template`, and `output_schema_name` fields, parsed from a `.md` file with YAML frontmatter.

- [ ] **Step 13.2**: Implement a `Prompt` dataclass and a tiny loader that reads `<name>.md` from the `prompts/` package directory, parses frontmatter (reusing `brain_core.vault.frontmatter.parse_frontmatter`), validates the `output_schema` field against `schemas.py` exports, and returns a typed `Prompt` object with `.render(**vars)` for user-template substitution (Python `str.format`-based, no Jinja, keep it boring).

- [ ] **Step 13.3**: Implement `schemas.py` with empty stub schemas that Tasks 14/15/16 will extend:
  ```python
  """Output schemas per prompt. Tasks 14-16 extend this module."""

  from __future__ import annotations

  from pydantic import BaseModel

  SCHEMAS: dict[str, type[BaseModel]] = {}
  ```

- [ ] **Step 13.4**: Create `docs/BRAIN.md.template` — a richly-commented template users can copy into `<vault>/BRAIN.md`. Include sections for taxonomy, naming conventions, wikilink rules, chat mode prompts (placeholders), and domain-specific guidance slots.

- [ ] **Step 13.5**: Gates + commit: `feat(brain_core): prompts package with .md loader and schema registry`.

---

## Task 14 — `summarize` prompt + schema + FakeLLMProvider test

**Files:**
- Create: `packages/brain_core/src/brain_core/prompts/summarize.md`
- Modify: `packages/brain_core/src/brain_core/prompts/schemas.py`
- Create: `packages/brain_core/tests/prompts/test_summarize.py`

- [ ] **Step 14.1**: Create `prompts/summarize.md` with frontmatter declaring `output_schema: SummarizeOutput`, a `## System` section with the system prompt (produce source-note frontmatter + body, 3–7 key points, entities mentioned, concepts raised, open questions), and a `## User Template` section with `{title}`, `{source_type}`, `{body}` placeholders.

- [ ] **Step 14.2**: Extend `schemas.py` with:
  ```python
  class SummarizeOutput(BaseModel):
      title: str
      summary: str
      key_points: list[str]
      entities: list[str]
      concepts: list[str]
      open_questions: list[str]

  SCHEMAS["SummarizeOutput"] = SummarizeOutput
  ```

- [ ] **Step 14.3**: Write a test that loads the prompt, renders it with an `ExtractedSource`-derived dict, feeds the render to a `FakeLLMProvider` whose queued response is a JSON string matching `SummarizeOutput`, parses the response via `SummarizeOutput.model_validate_json`, and asserts the round trip works.

- [ ] **Step 14.4**: Gates + commit: `feat(brain_core): summarize prompt + SummarizeOutput schema`.

---

## Task 15 — `integrate` prompt + PatchSet output + FakeLLMProvider test

**Files:**
- Create: `packages/brain_core/src/brain_core/prompts/integrate.md`
- Modify: `packages/brain_core/src/brain_core/prompts/schemas.py`
- Create: `packages/brain_core/tests/prompts/test_integrate.py`

- [ ] **Step 15.1**: Create `prompts/integrate.md` with frontmatter `output_schema: IntegrateOutput`, `## System` section instructing the model to produce a typed JSON patch set matching `brain_core.vault.types.PatchSet`, and a `## User Template` section with `{source_note}`, `{index_md}`, `{related_notes}` placeholders.

- [ ] **Step 15.2**: Add to `schemas.py`:
  ```python
  from brain_core.vault.types import PatchSet
  SCHEMAS["IntegrateOutput"] = PatchSet
  ```
  (We deliberately reuse the existing `PatchSet` model as the integrate output — one schema, one source of truth.)

- [ ] **Step 15.3**: Test: load the prompt, render, feed a `FakeLLMProvider` response that is a JSON string matching `PatchSet.model_dump_json()` of a simple hand-built `PatchSet`, parse via `PatchSet.model_validate_json`, assert round-trip produces an identical `PatchSet` to the one queued.

- [ ] **Step 15.4**: Gates + commit: `feat(brain_core): integrate prompt producing typed PatchSet output`.

---

## Task 16 — `classify` prompt + schema + test

**Files:**
- Create: `packages/brain_core/src/brain_core/prompts/classify.md`
- Create: `packages/brain_core/src/brain_core/ingest/classifier.py`
- Modify: `packages/brain_core/src/brain_core/prompts/schemas.py`
- Create: `packages/brain_core/tests/prompts/test_classify.py`
- Create: `packages/brain_core/tests/ingest/test_classifier.py`

- [ ] **Step 16.1**: `prompts/classify.md` produces `{source_type: ..., domain: research|work|personal, confidence: 0.0..1.0}` via a `ClassifyOutput` pydantic model.

- [ ] **Step 16.2**: Implement `ingest/classifier.py`:
  ```python
  """LLM-backed domain classifier. Falls back to explicit user routing if confidence < threshold."""

  from __future__ import annotations

  from dataclasses import dataclass

  from brain_core.llm.provider import LLMProvider
  from brain_core.llm.types import LLMMessage, LLMRequest
  from brain_core.prompts.loader import load_prompt
  from brain_core.prompts.schemas import SCHEMAS


  @dataclass(frozen=True)
  class ClassifyResult:
      source_type: str
      domain: str
      confidence: float
      needs_user_pick: bool


  async def classify(
      *,
      llm: LLMProvider,
      model: str,
      title: str,
      snippet: str,
      confidence_threshold: float = 0.7,
  ) -> ClassifyResult:
      prompt = load_prompt("classify")
      user = prompt.render(title=title, snippet=snippet)
      resp = await llm.complete(
          LLMRequest(
              model=model,
              system=prompt.system,
              messages=[LLMMessage(role="user", content=user)],
              max_tokens=256,
              temperature=0.0,
          )
      )
      out_model = SCHEMAS["ClassifyOutput"].model_validate_json(resp.content)
      return ClassifyResult(
          source_type=out_model.source_type,
          domain=out_model.domain,
          confidence=out_model.confidence,
          needs_user_pick=out_model.confidence < confidence_threshold,
      )
  ```

- [ ] **Step 16.3**: Write tests for both the prompt (parses, renders) and the classifier (FakeLLMProvider returns a known JSON, classifier produces expected `ClassifyResult`, low-confidence case flips `needs_user_pick=True`).

- [ ] **Step 16.4**: Gates + commit: `feat(brain_core): classify prompt + LLM-backed domain classifier`.

---

## Task 17 — Pipeline orchestrator (9 stages, FakeLLMProvider-driven)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/pipeline.py`
- Create: `packages/brain_core/tests/ingest/test_pipeline.py`

- [ ] **Step 17.1: Failing end-to-end test**

```python
# packages/brain_core/tests/ingest/test_pipeline.py
from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.vault.index import IndexFile
from brain_core.vault.types import PatchSet, IndexEntryPatch
from brain_core.vault.writer import VaultWriter


@pytest.mark.asyncio
async def test_ingest_text_end_to_end(ephemeral_vault: Path, fixtures_dir: Path) -> None:
    fake = FakeLLMProvider()
    # classify returns research
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    # summarize returns a well-formed source note body
    fake.queue(
        '{"title":"Hello","summary":"greeting","key_points":["hi"],"entities":[],"concepts":[],"open_questions":[]}'
    )
    # integrate returns a PatchSet
    patch = PatchSet(
        new_files=[],  # pipeline will add the source note itself; integrate only adds cross-refs
        index_entries=[IndexEntryPatch(section="Sources", line="- [[hello]] — greeting", domain="research")],
        log_entry="## [2026-04-13 12:00] ingest | source | [[hello]]",
        reason="test",
    )
    fake.queue(patch.model_dump_json())

    writer = VaultWriter(vault_root=ephemeral_vault)
    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=writer,
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )
    res = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert res.status is IngestStatus.OK
    assert res.note_path is not None
    assert res.note_path.exists()
    idx = IndexFile.load(ephemeral_vault / "research" / "index.md")
    assert any(e.target == "hello" for e in idx.sections["Sources"])
```

- [ ] **Step 17.2: Implement `pipeline.py`**

The orchestrator runs the 9 stages from the spec §5:

```python
"""IngestPipeline — 9-stage source-to-wiki orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from brain_core.ingest.archive import archive_dir_for
from brain_core.ingest.classifier import ClassifyResult, classify
from brain_core.ingest.dispatcher import dispatch
from brain_core.ingest.failures import record_failure
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, IngestResult, IngestStatus, SourceType
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import SCHEMAS
from brain_core.vault.frontmatter import serialize_with_frontmatter
from brain_core.vault.types import NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


@dataclass
class IngestPipeline:
    vault_root: Path
    writer: VaultWriter
    llm: LLMProvider
    summarize_model: str
    integrate_model: str
    classify_model: str

    async def ingest(
        self,
        spec: str | Path,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
    ) -> IngestResult:
        slug = self._slug_for(spec)
        try:
            handler = await dispatch(spec)
            now = datetime.now(tz=UTC)
            archive_dir = archive_dir_for(
                vault_root=self.vault_root,
                domain=domain_override or allowed_domains[0],
                when=now,
            )
            extracted = await handler.extract(spec, archive_root=archive_dir)
            # Idempotency: compute hash and check for existing note with the same hash
            chash = content_hash(extracted.body_text)
            if self._already_ingested(chash, allowed_domains):
                return IngestResult(status=IngestStatus.SKIPPED_DUPLICATE, note_path=None, extracted=extracted)

            if domain_override:
                domain = domain_override
                cls_result = ClassifyResult(
                    source_type=extracted.source_type.value,
                    domain=domain,
                    confidence=1.0,
                    needs_user_pick=False,
                )
            else:
                cls_result = await classify(
                    llm=self.llm,
                    model=self.classify_model,
                    title=extracted.title or slug,
                    snippet=extracted.body_text[:1000],
                )
                if cls_result.domain not in allowed_domains:
                    return IngestResult(
                        status=IngestStatus.QUARANTINED,
                        note_path=None,
                        extracted=extracted,
                        errors=[f"domain {cls_result.domain} not in allowed {allowed_domains}"],
                    )
                domain = cls_result.domain

            summary = await self._summarize(extracted)
            note_path, note_content = self._build_source_note(
                extracted=extracted, summary=summary, domain=domain, chash=chash, now=now
            )
            integrate_patch = await self._integrate(
                extracted=extracted, summary=summary, domain=domain
            )
            # Prepend the source note to the integrate patch's new_files
            integrate_patch.new_files.insert(0, NewFile(path=note_path, content=note_content))
            self.writer.apply(integrate_patch, allowed_domains=(domain,))
            return IngestResult(status=IngestStatus.OK, note_path=note_path, extracted=extracted)
        except Exception as exc:
            record_failure(vault_root=self.vault_root, slug=slug, stage="pipeline", exception=exc)
            return IngestResult(status=IngestStatus.FAILED, note_path=None, errors=[str(exc)])

    # ---- internals omitted for brevity in this plan; concrete code is generated in the implementer task ----

    def _slug_for(self, spec: str | Path) -> str:
        ...

    def _already_ingested(self, chash: str, domains: tuple[str, ...]) -> bool:
        ...

    async def _summarize(self, extracted: ExtractedSource) -> SCHEMAS["SummarizeOutput"]:  # type: ignore[name-defined]
        ...

    def _build_source_note(self, *, extracted, summary, domain, chash, now) -> tuple[Path, str]:
        ...

    async def _integrate(self, *, extracted, summary, domain) -> PatchSet:
        ...
```

**Concrete implementation details for the internal methods** (the implementer must fill these in, not leave them `...`):

- `_slug_for(spec)` — kebab-case from title/filename; date-prefix for sources.
- `_already_ingested(chash, domains)` — `rglob` over `<domain>/sources/*.md`, parse frontmatter, check `content_hash` field.
- `_summarize(extracted)` — renders `summarize.md`, calls `self.llm.complete(...)`, validates response via `SCHEMAS["SummarizeOutput"]`, returns typed model.
- `_build_source_note(...)` — assembles frontmatter dict (`title`, `domain`, `type=source`, `created`, `updated`, `source_type`, `source_url`, `content_hash`, `ingested_by`) and body (summary + key_points + entities + concepts + open_questions as markdown sections), serializes via `serialize_with_frontmatter`.
- `_integrate(...)` — renders `integrate.md`, calls `self.llm.complete(...)`, validates response via `PatchSet.model_validate_json`, returns `PatchSet`.

- [ ] **Step 17.3: Gates.** Expect ~100+ passed.

- [ ] **Step 17.4: Commit**: `feat(brain_core): 9-stage ingest pipeline with classify/summarize/integrate`.

---

## Task 18 — Idempotency regression test

**Files:**
- Create: `packages/brain_core/tests/ingest/test_idempotency.py`

- [ ] **Step 18.1: Test**

```python
@pytest.mark.asyncio
async def test_second_ingest_of_same_source_is_skipped(ephemeral_vault, fixtures_dir) -> None:
    # Queue enough responses for TWO full pipeline runs: classify+summarize+integrate each time.
    fake = FakeLLMProvider()
    # First run:
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue('{"title":"Hello","summary":"greeting","key_points":[],"entities":[],"concepts":[],"open_questions":[]}')
    fake.queue(PatchSet(log_entry="## [2026-04-13 12:00] ingest | [[hello]]").model_dump_json())
    # Second run should NOT consume any LLM calls.

    writer = VaultWriter(vault_root=ephemeral_vault)
    p = IngestPipeline(...)
    r1 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r1.status is IngestStatus.OK
    r2 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r2.status is IngestStatus.SKIPPED_DUPLICATE
    assert len(fake.requests) == 3  # not 6 — second run made no LLM calls
```

- [ ] **Step 18.2: Gates + commit**: `test(brain_core): verify ingest is idempotent via content_hash`.

---

## Task 19 — Bulk import with dry-run

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/bulk.py`
- Create: `packages/brain_core/tests/ingest/test_bulk.py`

- [ ] **Step 19.1**: Test: points at a temp folder with 3 text files, runs `bulk_import(folder, dry_run=True)`, asserts a `BulkPlan` is returned with 3 entries and no files have been written to the vault. Then `bulk_import(folder, dry_run=False)` (plus sufficient queued LLM responses) actually applies the plan.

- [ ] **Step 19.2: Implement `bulk.py`** with a `BulkPlan` dataclass (list of `BulkItem{spec, classified_domain, estimated_cost_usd}`), a `plan(folder)` method, and an `apply(plan)` method that calls `IngestPipeline.ingest` per item.

- [ ] **Step 19.3**: Gates + commit: `feat(brain_core): bulk import with dry-run plan + apply`.

---

## Task 20 — VCR infrastructure (cassette-based contract tests, optional)

**Files:**
- Modify: `packages/brain_core/pyproject.toml` — register `pytest-vcr` marker
- Create: `packages/brain_core/tests/prompts/conftest.py`
- Create: `packages/brain_core/tests/prompts/cassettes/.gitkeep`

- [ ] **Step 20.1**: Configure `pytest-vcr`:
  - Add `[tool.pytest.ini_options] markers = ["vcr: requires cassette"]`
  - In `tests/prompts/conftest.py`, configure `vcr` to use `tests/prompts/cassettes/` as the cassette dir and redact the `Authorization` header.
- [ ] **Step 20.2**: Document the two-mode pattern in `docs/testing/prompts-vcr.md`:
  - Normal mode: cassettes replay, no network, no key required.
  - Record mode: `RUN_LIVE_LLM_TESTS=1` re-records against real Anthropic API.
- [ ] **Step 20.3**: Gates + commit: `test(brain_core): VCR cassette infrastructure for prompt contract tests`.

---

## Task 21 — Record cassettes for summarize / integrate / classify (OPTIONAL, requires API key)

**Precondition:** `ANTHROPIC_API_KEY` is set in the environment.

- [ ] **Step 21.1**: Run `RUN_LIVE_LLM_TESTS=1 uv run pytest packages/brain_core/tests/prompts -v -m vcr` to record cassettes. Each cassette will be a YAML file under `tests/prompts/cassettes/`.
- [ ] **Step 21.2**: Redact any sensitive headers or bodies.
- [ ] **Step 21.3**: Commit cassettes: `test(brain_core): record Plan 02 prompt cassettes`.

**If API key is not available:** skip this task. Plan 02 does not require cassettes to merge. Mark as `⏸ deferred` in the plan status.

---

## Task 22 — Contract assertions on replayed cassettes

- [ ] **Step 22.1**: Write pytest-vcr-based tests that replay each cassette and assert:
  - Output JSON validates against the declared schema
  - `usage.input_tokens + usage.output_tokens` ≤ a generous budget (e.g., 8K) for each prompt
  - `summarize` output contains entities/concepts drawn from the input (sanity: shared tokens)
  - `integrate` output `PatchSet` validates and has at least one `index_entries` row
  - `classify` output domain ∈ {"research", "work", "personal"}
- [ ] **Step 22.2**: Gates + commit: `test(brain_core): contract assertions for summarize/integrate/classify cassettes`.

If cassettes are not committed (Task 21 deferred), these tests are decorated with `pytest.mark.skipif(not any(cassettes)...)` so the suite stays green.

---

## Task 23 — Cross-platform smoke (ingest edition)

- [ ] **Step 23.1**: Add tests to `test_cross_platform.py` (extends the existing Plan 01 file) or a new file for:
  - Text handler with unicode filename (`"héllo — ✓.txt"`)
  - PDF handler with unicode filename
  - Archive dir creation on Windows path separators (use the new `archive_dir_for` helper)
- [ ] **Step 23.2**: Gates + commit.

---

## Task 24 — Full sweep (coverage, mypy, ruff)

Same procedure as Plan 01 Task 21. Every gate must pass; coverage target is ≥ 85% on `brain_core` (Plan 01 left it at 92%; Plan 02 should keep it ≥ 85%). Fix any drift, commit style fixes separately.

---

## Task 25 — `scripts/demo-plan-02.py` end-to-end demo

**Files:**
- Create: `scripts/demo-plan-02.py`
- Create: `scripts/fixtures/` (mirror of the test fixtures, copied)

- [ ] **Step 25.1**: Write the demo script. It must:
  1. Create a temp vault (reuse the scaffold from `demo-plan-01.py`).
  2. Build an `IngestPipeline` with `FakeLLMProvider` and the production writer.
  3. Pre-queue all responses needed for 5 ingests (text, mocked URL via `respx`, PDF, VTT transcript, mocked tweet).
  4. Call `ingest(...)` for each fixture and assert the returned `IngestResult.status is OK`.
  5. Verify each source note exists, has `content_hash` frontmatter, and appears in the target domain's `index.md`.
  6. Run a second ingest of the same text fixture and assert `SKIPPED_DUPLICATE`.
  7. Assert `costs.sqlite` (or in-memory ledger tracking) has at least N rows.
  8. Print `PLAN 02 DEMO OK`.
- [ ] **Step 25.2**: Run the demo; capture the output.
- [ ] **Step 25.3**: Commit: `feat: plan 02 complete — ingest pipeline with passing demo`.

---

## Task 26 — Plan 02 closure

- [ ] **Step 26.1**: Update `tasks/todo.md`:
  - Flip Plan 02 status to `✅ Complete` with date + `plan-02-ingestion` tag.
  - If Task 21 (cassettes) was deferred, note it: `cassettes deferred; see Plan 02b when API key available`.
- [ ] **Step 26.2**: Append a Plan 02 closure entry to `tasks/lessons.md` summarizing: test count, coverage, any mypy/ruff drift found, any new lessons for Plan 03.
- [ ] **Step 26.3**: Tag:
  ```bash
  git commit -m "docs: close plan 02 (ingestion)"
  git tag plan-02-ingestion
  git log --oneline -5
  ```

---

## Verification checklist (reviewer gate at plan end)

- [ ] `uv run pytest packages/brain_core --cov=brain_core --cov-report=term-missing` — all pass, coverage ≥ 85%
- [ ] `cd packages/brain_core && uv run mypy src tests` — clean
- [ ] `uv run ruff check .` and `uv run ruff format --check .` — clean
- [ ] `uv run python scripts/demo-plan-02.py` — prints `PLAN 02 DEMO OK`
- [ ] CI green on Mac AND Windows after push
- [ ] No module outside `brain_core.ingest.handlers.url` or `...tweet` imports `httpx` directly (grep check)
- [ ] No module outside `brain_core.ingest.handlers.pdf` imports `fitz` directly
- [ ] No module outside `brain_core.ingest.handlers.transcript_docx` imports `docx` directly
- [ ] `content_hash` appears in every source note's frontmatter (grep `tests/ingest/test_pipeline.py` output)
- [ ] `tasks/lessons.md` updated with any Plan 02 corrections
- [ ] `plan-02-ingestion` tag exists

---

## Self-review notes (pre-execution)

- **Spec coverage**: implements spec §5 (ingestion pipeline) fully for day-one source types. Bulk import from spec §5 "Bulk import mode" landed here. Prompts spec §7-adjacent behavior (summarize/integrate/classify) implemented with typed outputs. No chat / MCP / API / web / install behavior touched.
- **Deferred from Plan 01**: VaultWriter rollback hardening and UndoLog byte-count parsing are NOT fixed in Plan 02. If bulk import or ingest volume exposes concrete failures, add a Task 19a to address them. Otherwise they remain deferred per `tasks/lessons.md`.
- **No real API calls in CI**: every test uses `FakeLLMProvider`, `respx`, or file fixtures. Cassette-based contract tests (Tasks 20–22) are optional and cleanly skipped if cassettes aren't present.
- **New 3rd-party deps**: `httpx`, `trafilatura`, `pymupdf`, `webvtt-py`, `python-docx` at runtime; `respx`, `vcrpy`, `pytest-vcr` in dev. Some of these (notably `trafilatura`, `fitz`, `docx`) will need `# type: ignore[import-untyped]` at the single import site or per-module mypy overrides — track as lessons if they do.
- **Per-task discipline**: every implementer task runs the full per-task self-review checklist (pytest, mypy, ruff, ruff format, git status). This is the hardened rhythm from Plan 01's Task 21 retrospective.
- **Type consistency**: `ExtractedSource`, `IngestResult`, `IngestStatus`, `PatchSet`, `NewFile`, `Edit`, `IndexEntryPatch`, `ClassifyResult`, `SummarizeOutput` are each defined exactly once and imported everywhere they're used. The pipeline's `_build_source_note` is the one place that converts an `ExtractedSource` + `SummarizeOutput` into a vault-ready note string; no parallel implementations.
- **Scope**: this plan is sized for one subagent-driven-development pass. It produces `brain add` behavior via a demo script (the CLI proper lives in Plan 08). Plan 02's exit state: anyone can write a 30-line Python driver that ingests a folder of mixed sources into a real `~/Documents/brain/` vault.

---

**End of Plan 02.**
