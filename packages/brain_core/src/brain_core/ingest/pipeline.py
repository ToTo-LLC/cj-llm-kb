"""IngestPipeline — 9-stage source-to-wiki orchestrator.

Task 17A lands the pure helper methods and the class skeleton. Task 17B fills
in the async `ingest()` method and wires the LLM round-trips.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from brain_core.config.schema import DEFAULT_DOMAINS
from brain_core.cost.budget import BudgetEnforcer
from brain_core.ingest.archive import archive_dir_for
from brain_core.ingest.classifier import ClassifyResult
from brain_core.ingest.dispatcher import dispatch
from brain_core.ingest.failures import record_failure
from brain_core.ingest.handlers.base import SourceHandler
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, IngestResult, IngestStatus
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest, LLMResponse
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput, SummarizeOutput
from brain_core.state.db import StateDB
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
    # Plan 07 Task 4: optional StateDB so ``ingest()`` can append a row to
    # ``ingest_history`` after each run. Defaults to ``None`` so every Plan 02
    # call site (tests, demo scripts) keeps compiling without change. When
    # absent, ``_record_history`` is a no-op.
    state_db: StateDB | None = None
    # Issue #23: optional handler list. When provided, ``ingest()`` passes
    # it to ``dispatch(...)`` so config-supplied handler tunables (URL/Tweet
    # timeouts, PDF min_chars) take effect. ``None`` falls back to
    # ``_default_handlers()`` with hardcoded defaults — keeps Plan 02 call
    # sites working unchanged.
    handlers: list[SourceHandler] | None = None

    async def ingest(
        self,
        spec: str | Path,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
        apply: bool = True,
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

        Args:
            apply: When True (default), Stage 9 writes the PatchSet via
                ``self.writer.apply(...)`` and returns an ``IngestResult`` with
                ``patchset=None`` — matches pre-apply-kwarg behavior. When
                False, Stage 9 is skipped: the built PatchSet is returned on
                ``IngestResult.patchset`` and the vault is NOT mutated. The
                caller is then responsible for either applying the patch
                (``writer.apply(patchset, allowed_domains=(result.note_path.parts[<domain>],))``)
                or staging it via ``PendingPatchStore.put(...)``. Status paths
                other than OK (SKIPPED_DUPLICATE / QUARANTINED / FAILED) are
                unaffected by this flag — they never produce a patchset.
        """
        now = datetime.now(tz=UTC)

        # Stage 1: preliminary slug — must be outside try so it's always bound
        # in the except handler for record_failure.
        slug = self._slug_for(spec)

        # Issue #29: accumulate per-stage USD spend so the row written into
        # ``ingest_history`` carries a real ``cost_usd`` rather than the
        # placeholder 0.0. Stages 2-4 are LLM-free so they contribute nothing;
        # the classify / summarize / integrate stages each add their estimated
        # cost. Cost is tracked even on early-return paths (QUARANTINED,
        # FAILED, etc.) so partial spend is still recorded.
        run_cost: float = 0.0

        try:
            # Stage 2: Dispatch — pass self.handlers so config-supplied
            # handler tunables (issue #23) flow through.
            handler = await dispatch(spec, handlers=self.handlers)

            # Stage 3: Archive dir + Extract
            tentative_domain = domain_override if domain_override else allowed_domains[0]
            archive_dir = archive_dir_for(
                vault_root=self.vault_root, domain=tentative_domain, when=now
            )
            extracted = await handler.extract(spec, archive_root=archive_dir)

            # Stage 4: Content hash + Idempotency
            chash = content_hash(extracted.body_text)
            if self._already_ingested(chash, allowed_domains):
                self._record_history(
                    source=str(spec),
                    source_type=extracted.source_type.value,
                    domain=tentative_domain,
                    status=IngestStatus.SKIPPED_DUPLICATE.value,
                    patch_id=None,
                    error=None,
                    cost_usd=run_cost,
                )
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
                cls_result, classify_cost = await self._classify_with_cost(
                    title=extracted.title or slug,
                    snippet=extracted.body_text[:1000],
                )
                run_cost += classify_cost
            domain = cls_result.domain
            if domain not in allowed_domains:
                self._record_history(
                    source=str(spec),
                    source_type=extracted.source_type.value,
                    domain=domain,
                    status=IngestStatus.QUARANTINED.value,
                    patch_id=None,
                    error=f"domain {domain!r} not in allowed {allowed_domains}",
                    cost_usd=run_cost,
                )
                return IngestResult(
                    status=IngestStatus.QUARANTINED,
                    note_path=None,
                    extracted=extracted,
                    errors=[f"domain {domain!r} not in allowed {allowed_domains}"],
                )

            # Stage 6: Summarize
            summary, summarize_cost = await self._summarize(extracted)
            run_cost += summarize_cost

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
            integrate_patch, integrate_cost = await self._integrate(
                extracted=extracted,
                summary=summary,
                domain=domain,
                note_content=note_content,
            )
            run_cost += integrate_cost
            integrate_patch.new_files.insert(0, NewFile(path=note_path, content=note_content))

            # Stage 9: Apply (or stage)
            if apply:
                receipt = self.writer.apply(integrate_patch, allowed_domains=(domain,))
                self._record_history(
                    source=str(spec),
                    source_type=extracted.source_type.value,
                    domain=domain,
                    status=IngestStatus.OK.value,
                    patch_id=receipt.undo_id,
                    error=None,
                    cost_usd=run_cost,
                )
                return IngestResult(
                    status=IngestStatus.OK,
                    note_path=note_path,
                    extracted=extracted,
                )
            # apply=False — return the PatchSet for the caller to stage/apply.
            # note_path is the INTENDED path; nothing has been written.
            self._record_history(
                source=str(spec),
                source_type=extracted.source_type.value,
                domain=domain,
                status=IngestStatus.OK.value,
                patch_id=None,
                error=None,
                cost_usd=run_cost,
            )
            return IngestResult(
                status=IngestStatus.OK,
                note_path=note_path,
                extracted=extracted,
                patchset=integrate_patch,
            )

        except Exception as exc:
            record_failure(
                vault_root=self.vault_root,
                slug=slug,
                stage="pipeline",
                exception=exc,
            )
            self._record_history(
                source=str(spec),
                source_type=None,
                domain=None,
                status=IngestStatus.FAILED.value,
                patch_id=None,
                error=str(exc),
                cost_usd=run_cost,
            )
            return IngestResult(
                status=IngestStatus.FAILED,
                note_path=None,
                errors=[str(exc)],
            )

    async def _classify_with_cost(
        self, *, title: str, snippet: str
    ) -> tuple[ClassifyResult, float]:
        """Run the classify prompt inline and return (result, cost_usd).

        Pipeline-private variant of :func:`brain_core.ingest.classifier.classify`
        — keeps the public free function unchanged for other callers
        (BulkImporter, the standalone classify tool, contract tests) while
        giving the pipeline access to the response usage so it can charge
        the spend to ``ingest_history.cost_usd`` (issue #29).

        Plan 10 Task 3 routes the prompt's domain enum through
        :meth:`Prompt.render_system` and validates the LLM reply with the
        per-call ``allowed_domains`` context. Task 4 swaps
        ``DEFAULT_DOMAINS`` here for the live ingest scope so user-added
        domains actually appear in the enum.
        """
        prompt = load_prompt("classify")
        domains_text = ", ".join(f"`{d}`" for d in DEFAULT_DOMAINS)
        system = prompt.render_system(domains=domains_text)
        user_content = prompt.render(title=title, snippet=snippet)
        response = await self.llm.complete(
            LLMRequest(
                model=self.classify_model,
                system=system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=256,
                temperature=0.0,
            )
        )
        parsed = json.loads(response.content)
        out = ClassifyOutput.model_validate(
            parsed,
            context={"allowed_domains": list(DEFAULT_DOMAINS)},
        )
        result = ClassifyResult(
            source_type=out.source_type,
            domain=out.domain,
            confidence=out.confidence,
            needs_user_pick=out.confidence < 0.7,
        )
        return result, _estimate_call_cost(self.classify_model, response)

    async def _summarize(self, extracted: ExtractedSource) -> tuple[SummarizeOutput, float]:
        """Call the summarize prompt and parse the response as SummarizeOutput.

        Returns ``(parsed, cost_usd)`` so the pipeline can accumulate spend
        per stage (issue #29).
        """
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
        parsed = SummarizeOutput.model_validate_json(response.content)
        return parsed, _estimate_call_cost(self.summarize_model, response)

    async def _integrate(
        self,
        *,
        extracted: ExtractedSource,
        summary: SummarizeOutput,
        domain: str,
        note_content: str,
    ) -> tuple[PatchSet, float]:
        """Call the integrate prompt and parse the response as a PatchSet.

        Feeds the integrate LLM the rendered markdown body of the source note
        (not the SummarizeOutput JSON) so wikilink generation and section
        references work against the same prose the vault will eventually hold.

        Returns ``(parsed, cost_usd)`` so the pipeline can accumulate spend
        per stage (issue #29).
        """
        prompt = load_prompt("integrate")
        index_path = self.vault_root / domain / "index.md"
        index_md = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
        # TODO: related-notes retrieval lands in a later plan.
        user_content = prompt.render(
            source_note=note_content,
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
        parsed = PatchSet.model_validate_json(response.content)
        return parsed, _estimate_call_cost(self.integrate_model, response)

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

    def _record_history(
        self,
        *,
        source: str,
        source_type: str | None,
        domain: str | None,
        status: str,
        patch_id: str | None,
        error: str | None,
        cost_usd: float = 0.0,
    ) -> None:
        """Append a row to ``ingest_history`` (Plan 07 Task 4).

        Best-effort: any sqlite error is swallowed so a write-side failure
        cannot break the ingest pipeline. Logs the failure via stderr so
        operators still see it. ``state_db is None`` short-circuits — Plan
        02 call sites that never wired a StateDB still work unchanged.

        ``cost_usd`` defaults to 0.0 so non-LLM exit paths (e.g. duplicate
        skip before any classify call) still write a row without spurious
        spend (issue #29).
        """
        if self.state_db is None:
            return
        # ``ingest_history`` is observability, not correctness — a sqlite
        # failure here must NOT break the pipeline. Suppress broadly so a
        # malformed schema, locked DB, or missing migration degrades to
        # silent skip rather than a user-visible ingest failure.
        with contextlib.suppress(Exception):
            self.state_db.exec(
                "INSERT INTO ingest_history "
                "(source, source_type, domain, status, patch_id, classified_at, cost_usd, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source,
                    source_type,
                    domain,
                    status,
                    patch_id,
                    datetime.now(tz=UTC).isoformat(),
                    cost_usd,
                    error,
                ),
            )

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


def _estimate_call_cost(model: str, response: LLMResponse) -> float:
    """Return USD cost for ``response`` priced at ``model``'s rates.

    Wraps :meth:`BudgetEnforcer.estimate_cost` and degrades to 0.0 when the
    pricing table doesn't know the model. We don't want an unrecognized
    model (e.g. a fake LLM model string in a test) to crash the ingest
    pipeline — the recorded cost being 0 in that case is the same shape
    callers see for non-LLM exit paths (issue #29).
    """
    try:
        return BudgetEnforcer.estimate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    except KeyError:
        return 0.0


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
