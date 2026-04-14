"""IngestPipeline — 9-stage source-to-wiki orchestrator.

Task 17A lands the pure helper methods and the class skeleton. Task 17B fills
in the async `ingest()` method and wires the LLM round-trips.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from brain_core.ingest.types import ExtractedSource, IngestResult
from brain_core.llm.provider import LLMProvider
from brain_core.vault.frontmatter import parse_frontmatter, serialize_with_frontmatter
from brain_core.vault.writer import VaultWriter

if TYPE_CHECKING:
    from brain_core.prompts.schemas import SummarizeOutput


@dataclass
class IngestPipeline:
    """Source-to-wiki ingest pipeline. Uses a dispatcher, handler, classifier, and prompts."""

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
        """Full pipeline. Implemented in Task 17B."""
        raise NotImplementedError("IngestPipeline.ingest() lands in Task 17B")

    # ---- Pure helpers (this batch) ----

    def _slug_for(self, spec: str | Path, *, title: str | None = None) -> str:
        """Return a kebab-case slug for the source note filename.

        Priority:
        1. If `title` is provided and non-empty, slugify it.
        2. Else if `spec` is a Path, use `spec.stem`.
        3. Else if `spec` is a str URL (http/https), use the last non-empty
           path segment. Fall back to the netloc.
        4. Else (plain text string), use the first 60 characters of the first
           non-empty line.
        """
        candidate = self._choose_slug_source(spec, title)
        slug = _kebabify(candidate)
        if not slug:
            slug = "source"
        return slug[:80]  # hard cap

    @staticmethod
    def _choose_slug_source(spec: str | Path, title: str | None) -> str:
        if title and title.strip():
            return title
        if isinstance(spec, Path):
            return spec.stem
        # str input
        parsed = urlparse(spec)
        if parsed.scheme in {"http", "https"}:
            segments = [seg for seg in parsed.path.split("/") if seg]
            if segments:
                return segments[-1]
            if parsed.netloc:
                return parsed.netloc
        # Fallback: first non-empty line, 60 chars
        for line in spec.splitlines():
            line = line.strip()
            if line:
                return line[:60]
        return "source"

    def _already_ingested(self, chash: str, domains: tuple[str, ...]) -> bool:
        """Return True if any source note in `domains` has matching `content_hash` frontmatter.

        Iterates `<vault_root>/<domain>/sources/*.md` non-recursively (the pipeline
        always writes source notes directly under `sources/`). Reads each file,
        parses frontmatter, compares `content_hash`. Skips files whose frontmatter
        is malformed (defensive — a bad note must not poison dedup).
        """
        for domain in domains:
            sources_dir = self.vault_root / domain / "sources"
            if not sources_dir.is_dir():
                continue
            for note_path in sources_dir.glob("*.md"):
                try:
                    content = note_path.read_text(encoding="utf-8")
                    fm, _body = parse_frontmatter(content)
                except Exception:
                    continue  # malformed frontmatter = not a match, keep looking
                if fm.get("content_hash") == chash:
                    return True
        return False

    def _build_source_note(
        self,
        *,
        extracted: ExtractedSource,
        summary: SummarizeOutput,
        domain: str,
        chash: str,
        now: datetime,
        slug: str,
    ) -> tuple[Path, str]:
        """Build the canonical source note: frontmatter + structured markdown body.

        Returns `(note_path, note_content)`. `note_path` is
        `<vault_root>/<domain>/sources/<slug>.md`.

        Frontmatter fields written:
            title, domain, type=source, created, updated, source_type,
            source_url, content_hash, ingested_by

        Body sections (markdown):
            # <title>
            <summary>
            ## Key points
            - ...
            ## Entities
            - ...
            ## Concepts
            - ...
            ## Open questions
            - ...

        Empty lists render as `_(none)_`.
        """
        note_path = self.vault_root / domain / "sources" / f"{slug}.md"
        fm: dict[str, object] = {
            "title": summary.title,
            "domain": domain,
            "type": "source",
            "created": now.date().isoformat(),
            "updated": now.date().isoformat(),
            "source_type": extracted.source_type.value,
            "source_url": extracted.source_url,
            "content_hash": chash,
            "ingested_by": "brain",
        }
        body = _render_source_body(summary=summary)
        content = serialize_with_frontmatter(fm, body=body)
        return note_path, content


def _kebabify(text: str) -> str:
    """Lowercase, replace runs of non-alphanumeric chars with a single '-', strip ends."""
    lowered = text.lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lowered)
    return kebab.strip("-")


def _render_source_body(*, summary: SummarizeOutput) -> str:
    """Render the markdown body of a source note from a SummarizeOutput.

    Imported lazily-ish — the actual type hint refers to
    `brain_core.prompts.schemas.SummarizeOutput`. We use a string annotation
    and TYPE_CHECKING import to avoid a circular or load-order issue.
    """
    lines: list[str] = [
        f"# {summary.title}",
        "",
        summary.summary,
        "",
        "## Key points",
        "",
    ]
    if summary.key_points:
        lines.extend(f"- {p}" for p in summary.key_points)
    else:
        lines.append("_(none)_")
    lines.extend(("", "## Entities", ""))
    if summary.entities:
        lines.extend(f"- {e}" for e in summary.entities)
    else:
        lines.append("_(none)_")
    lines.extend(("", "## Concepts", ""))
    if summary.concepts:
        lines.extend(f"- {c}" for c in summary.concepts)
    else:
        lines.append("_(none)_")
    lines.extend(("", "## Open questions", ""))
    if summary.open_questions:
        lines.extend(f"- {q}" for q in summary.open_questions)
    else:
        lines.append("_(none)_")
    return "\n".join(lines) + "\n"
