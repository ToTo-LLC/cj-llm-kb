"""IngestPipeline — 9-stage source-to-wiki orchestrator.

Task 17A lands the pure helper methods and the class skeleton. Task 17B fills
in the async `ingest()` method and wires the LLM round-trips.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from brain_core.ingest.archive import archive_dir_for
from brain_core.ingest.classifier import ClassifyResult, classify
from brain_core.ingest.dispatcher import dispatch
from brain_core.ingest.failures import record_failure
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, IngestResult, IngestStatus
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import parse_frontmatter, serialize_with_frontmatter
from brain_core.vault.types import NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


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
        """Full 9-stage source-to-wiki pipeline.

        Stages:
            1. Slug        — preliminary slug from spec (no title yet).
            2. Dispatch    — resolve a SourceHandler for the spec.
            3. Archive dir + Extract — compute archive dir; extract source.
            4. Content hash + Idempotency — skip if already ingested.
            5. Classify (or override) — determine domain; quarantine on mismatch.
            6. Summarize   — LLM summarize round-trip.
            7. Build source note — recompute slug using summary title.
            8. Integrate   — LLM integrate round-trip → PatchSet.
            9. Apply       — write vault; return IngestResult.

        The entire body (stages 2-9) is wrapped in a broad exception handler
        that records a .error.json failure record and returns FAILED.
        """
        now = datetime.now(tz=UTC)

        # Stage 1: preliminary slug — must be outside try so it's always bound
        # in the except handler for record_failure.
        slug = self._slug_for(spec)

        try:
            # Stage 2: Dispatch
            handler = await dispatch(spec)

            # Stage 3: Archive dir + Extract
            tentative_domain = domain_override if domain_override else allowed_domains[0]
            archive_dir = archive_dir_for(
                vault_root=self.vault_root, domain=tentative_domain, when=now
            )
            extracted = await handler.extract(spec, archive_root=archive_dir)

            # Stage 4: Content hash + Idempotency
            chash = content_hash(extracted.body_text)
            if self._already_ingested(chash, allowed_domains):
                return IngestResult(
                    status=IngestStatus.SKIPPED_DUPLICATE,
                    note_path=None,
                    extracted=extracted,
                )

            # Stage 5: Classify (or override)
            if domain_override is not None:
                cls_result = ClassifyResult(
                    source_type=extracted.source_type.value,
                    domain=domain_override,
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
            domain = cls_result.domain
            if domain not in allowed_domains:
                return IngestResult(
                    status=IngestStatus.QUARANTINED,
                    note_path=None,
                    extracted=extracted,
                    errors=[f"domain {domain!r} not in allowed {allowed_domains}"],
                )

            # Stage 6: Summarize
            summary = await self._summarize(extracted)

            # Stage 7: Build source note — recompute slug with summary title
            slug = self._slug_for(spec, title=summary.title)
            note_path, note_content = self._build_source_note(
                extracted=extracted,
                summary=summary,
                domain=domain,
                chash=chash,
                now=now,
                slug=slug,
            )

            # Stage 8: Integrate → PatchSet; prepend source note
            integrate_patch = await self._integrate(
                extracted=extracted, summary=summary, domain=domain
            )
            integrate_patch.new_files.insert(0, NewFile(path=note_path, content=note_content))

            # Stage 9: Apply
            self.writer.apply(integrate_patch, allowed_domains=(domain,))
            return IngestResult(
                status=IngestStatus.OK,
                note_path=note_path,
                extracted=extracted,
            )

        except Exception as exc:
            record_failure(
                vault_root=self.vault_root,
                slug=slug,
                stage="pipeline",
                exception=exc,
            )
            return IngestResult(
                status=IngestStatus.FAILED,
                note_path=None,
                errors=[str(exc)],
            )

    async def _summarize(self, extracted: ExtractedSource) -> SummarizeOutput:
        """Call the summarize prompt and parse the response as SummarizeOutput."""
        prompt = load_prompt("summarize")
        user_content = prompt.render(
            title=extracted.title or "",
            source_type=extracted.source_type.value,
            body=extracted.body_text,
        )
        response = await self.llm.complete(
            LLMRequest(
                model=self.summarize_model,
                system=prompt.system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=2048,
                temperature=0.2,
            )
        )
        return SummarizeOutput.model_validate_json(response.content)

    async def _integrate(
        self,
        *,
        extracted: ExtractedSource,
        summary: SummarizeOutput,
        domain: str,
    ) -> PatchSet:
        """Call the integrate prompt and parse the response as a PatchSet."""
        prompt = load_prompt("integrate")
        index_path = self.vault_root / domain / "index.md"
        index_md = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
        # TODO: related-notes retrieval lands in a later plan.
        user_content = prompt.render(
            source_note=summary.model_dump_json(indent=2),
            index_md=index_md,
            domain=domain,
            related_notes="",
        )
        response = await self.llm.complete(
            LLMRequest(
                model=self.integrate_model,
                system=prompt.system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=2048,
                temperature=0.2,
            )
        )
        return PatchSet.model_validate_json(response.content)

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
