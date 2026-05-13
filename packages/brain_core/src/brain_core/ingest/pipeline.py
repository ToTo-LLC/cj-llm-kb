"""IngestPipeline — 9-stage source-to-wiki orchestrator.

Task 17A lands the pure helper methods and the class skeleton. Task 17B fills
in the async `ingest()` method and wires the LLM round-trips.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

from brain_core.budget import BudgetCapExceeded, PerDomainBudgetGuard
from brain_core.config.schema import Config
from brain_core.cost.budget import BudgetEnforcer
from brain_core.cost.ledger import CostLedger
from brain_core.ingest.archive import archive_dir_for
from brain_core.ingest.classifier import ClassifyResult
from brain_core.ingest.dispatcher import dispatch
from brain_core.ingest.failures import record_failure
from brain_core.ingest.handlers.base import SourceHandler
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.ocr import ocr_image
from brain_core.ingest.types import ExtractedSource, IngestResult, IngestStatus, SourceType
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest, LLMResponse
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput, SummarizeOutput
from brain_core.state.db import StateDB
from brain_core.vault.frontmatter import (
    Frontmatter,
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.log import LogEntry, LogFile
from brain_core.vault.paths import ScopeError, scope_guard
from brain_core.vault.types import Edit, IndexEntryPatch, NewFile, PatchSet
from brain_core.vault.writer import Receipt, VaultWriter

_log = structlog.get_logger(__name__)


# Plan 25 T2: OCR-marker pattern for the content-sniff D15 exception.
# Matches OCR block markers inserted by:
#   - Plan 24 T4 DocxHandler images:      [Image: <text>]
#   - Plan 24 T4 PptxHandler slide images: [Image (slide N): <text>]
#   - Plan 25 T3 PDFHandler page renders:  [Page N: <text>]
# When a body carries any of these, ``_looks_like_meaningful_text`` skips
# its 200-char ``min_chars`` floor (OCR-heavy sources are NOT near-empty
# regardless of post-OCR length). Printable + letter-ratio checks still
# apply so binary nonsense with a fake ``[Image: `` prefix still rejects.
_OCR_MARKER_PATTERN = re.compile(
    r"\[(?:Image(?:\s+\(slide\s+\d+\))?|Page\s+\d+):\s"
)


# Plan 25 T2: source-type set the Stage 3.5 sniff applies to. URL + EMAIL +
# TWEET are excluded — those handlers produce highly structured output
# (HTML-derived prose, RFC822-derived headers+body, JSON-derived prose)
# that wouldn't benefit from the same heuristic and may legitimately
# emit short bodies. Sniff those separately if a future plan needs it.
_TEXT_SHAPED_SOURCE_TYPES: frozenset[SourceType] = frozenset({
    SourceType.TEXT,
    SourceType.TRANSCRIPT,
    SourceType.DOCX,
    SourceType.PPTX,
    SourceType.PDF,
})


def _looks_like_meaningful_text(body_text: str, *, min_chars: int = 200) -> bool:
    """Cheap heuristic: does ``body_text`` look like human-readable content?

    Catches binary nonsense masquerading as text, base64 dumps without
    context, encrypted blobs, etc. Passes legitimate technical docs, code
    samples, multi-language content. Used by :meth:`IngestPipeline.ingest`
    Stage 3.5 (Plan 25 T2) to short-circuit clearly-non-meaningful files
    BEFORE any LLM call.

    Thresholds per Plan 25 D3:

    * ``len(body_text) >= min_chars`` (default 200) — SKIPPED when body
      contains OCR block markers per D15 (OCR-heavy sources are not
      near-empty regardless of post-OCR length).
    * non-whitespace content >= ``min_chars / 2`` — only when ``min_chars``
      applies (i.e. skipped under the D15 OCR-marker exception).
    * printable ratio >= 80% — printable ASCII or Unicode letters /
      digits / whitespace / punctuation (per ``str.isprintable``); excludes
      control chars + raw binary bytes. ALWAYS applies, including under
      D15. Catches binary nonsense with a fake ``[Image: `` prefix.
    * letter ratio >= 40% (per ``str.isalpha``, which includes non-ASCII
      Unicode letters so multi-language content passes). ALWAYS applies,
      including under D15.

    Empty bodies always return ``False`` — there's nothing to ingest.
    """
    if len(body_text) == 0:
        return False

    has_ocr_markers = bool(_OCR_MARKER_PATTERN.search(body_text))

    # Threshold 1: min char count — skipped when OCR markers present (D15).
    if not has_ocr_markers and len(body_text) < min_chars:
        return False

    # Threshold 2: non-whitespace content — only when min_chars applies.
    if not has_ocr_markers:
        non_ws = "".join(c for c in body_text if not c.isspace())
        if len(non_ws) < min_chars / 2:
            return False  # too much whitespace = effectively empty

    # Threshold 3: printable ratio (ALWAYS applies — including under D15).
    printable = sum(1 for c in body_text if c.isprintable())
    if printable / len(body_text) < 0.8:
        return False

    # Threshold 4: letter ratio (ALWAYS applies — including under D15).
    # ``str.isalpha`` includes non-ASCII Unicode letters so multi-language
    # content passes naturally.
    letters = sum(1 for c in body_text if c.isalpha())
    if letters / len(body_text) < 0.4:
        return False

    return True


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
    # Plan 16 Task 28.5: optional per-domain budget guard, called BEFORE
    # every LLM round-trip (classify, summarize, integrate). When ``None``,
    # no per-domain enforcement runs — every Plan 02 call site that
    # constructed an ``IngestPipeline`` without a guard keeps compiling
    # unchanged. The classify call uses ``domain_override`` (when supplied)
    # as the per-call domain — the auto-detect path can't know the domain
    # before classify runs, so the guard no-ops there. Summarize and
    # integrate use the resolved domain.
    guard: PerDomainBudgetGuard | None = None
    # Plan 16 Task 28.5: optional Config so the per-domain guard can read
    # ``config.budget.per_domain[domain]``. The pipeline doesn't read any
    # other Config fields — model selection still flows in via the
    # ``classify_model`` / ``summarize_model`` / ``integrate_model``
    # dataclass fields, populated by the caller.
    config: Config | None = None
    # Plan 24 Task 4: optional CostLedger so the post-classify OCR pass
    # (DocxHandler + PptxHandler images via :func:`brain_core.ingest.ocr.ocr_image`)
    # can record ``operation="ocr"`` rows + the per-domain guard can count
    # OCR spend against the per-domain cap. When ``None`` (or when
    # ``guard`` / ``config`` are also ``None``), the OCR pass is skipped
    # entirely — handler extraction still runs, but image text is NOT
    # inlined into ``body_text``. Every pre-Plan-24 call site that
    # constructed an ``IngestPipeline`` without a ledger keeps compiling.
    cost_ledger: CostLedger | None = None

    async def ingest(
        self,
        spec: str | Path,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
        apply: bool = True,
        source_path: Path | None = None,
        watched_folder_id: str | None = None,
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
            source_path: Plan 22 T10.5. Optional absolute path on disk of
                the local source file being ingested. When set, the source
                note's frontmatter carries ``source_path`` (resolved string
                form) — required for T6 ``WatchedFolderWatcher`` lookup so
                subsequent modify/delete events can re-ingest the SAME note
                (via :meth:`update_source`) or mark it orphaned (via
                :meth:`mark_orphaned`). Callers that ingest URL / paste /
                direct-text content MUST leave this ``None`` — the field is
                spec-defined as "only set when ingestion came from a local
                file" (per :class:`brain_core.vault.frontmatter.Frontmatter`).
                Default ``None`` preserves pre-T10.5 behavior for all
                non-watched-folder call sites (drag-drop, MCP ingest tool,
                bulk import without watch context).
            watched_folder_id: Plan 22 T10.5. Optional ``WatchedFolder.path``
                string identifying the watched folder that triggered this
                ingest. When set, the source note's frontmatter carries
                ``watched_folder_id`` — required for T6
                ``WatchedFolderWatcher._index_vault_for_folder`` to filter
                vault notes back to their originating watched folder.
                Default ``None`` preserves pre-T10.5 behavior for all
                non-watched-folder call sites.
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

            # Stage 3.5: Content sniff (Plan 25 T2)
            # ------------------------------------------------------------------
            # For text-shaped sources (text, transcript, docx, pptx, pdf), screen
            # the extracted body against cheap stdlib heuristics. Non-meaningful
            # content (binary nonsense, encrypted blobs, base64 dumps without
            # context) quarantines to ``raw/inbox/failed/<slug>.needs_review.json``
            # without burning LLM tokens on classify / summarize / integrate.
            #
            # D15 OCR-aware exception: bodies carrying ``[Image:`` / ``[Image
            # (slide N):`` / ``[Page N:`` markers (Plan 24 T4 docx/pptx OCR,
            # Plan 25 T3 pdf page renders) skip the 200-char min floor — OCR-
            # heavy sources are NOT near-empty regardless of post-OCR length.
            # Printable + letter-ratio checks still apply so binary nonsense
            # with a fake marker prefix still rejects.
            #
            # Cost rail: Stage 3.5 fires BEFORE any LLM call so no
            # ``PerDomainBudgetGuard.check_for`` is needed at this seam — the
            # sniff is a free pre-screen, and stages 4-9 are skipped entirely
            # on quarantine.
            if extracted.source_type in _TEXT_SHAPED_SOURCE_TYPES:
                if not _looks_like_meaningful_text(extracted.body_text):
                    self._quarantine_content_sniff(
                        spec=spec,
                        slug=slug,
                        extracted=extracted,
                    )
                    self._record_history(
                        source=str(spec),
                        source_type=extracted.source_type.value,
                        domain=None,
                        status=IngestStatus.FAILED.value,
                        patch_id=None,
                        error="content_sniff: non_meaningful_text",
                        cost_usd=run_cost,
                    )
                    return IngestResult(
                        status=IngestStatus.FAILED,
                        note_path=None,
                        extracted=extracted,
                        errors=[
                            "content_sniff: text does not appear meaningful "
                            "(non_meaningful_text)"
                        ],
                    )

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
                    allowed_domains=allowed_domains,
                    domain=domain_override,
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

            # Stage 5.5: OCR images (Plan 24 T4)
            # ----------------------------------------------------------
            # Post-classify so the ledger row + budget gate run against
            # the RESOLVED domain (quarantined ingests skip OCR entirely
            # — the early-return above bypasses this block). Pre-summarize
            # so the inlined ``[Image: ...]`` blocks feed the summarize +
            # integrate prompts. Idempotency hash (Stage 4) is computed on
            # the pre-OCR body, so re-ingesting the same source skips OCR
            # too — duplicate detection happens before any vision spend.
            extracted = await self._ocr_images(extracted, domain=domain)

            # Stage 6: Summarize
            summary, summarize_cost = await self._summarize(extracted, domain=domain)
            run_cost += summarize_cost

            # Stage 7: Build source note — recompute slug with summary title.
            # Plan 22 T10.5: thread the optional watched-context kwargs so
            # the source note's frontmatter carries ``source_path`` +
            # ``watched_folder_id`` when the caller (T5 bulk import via
            # ``brain_watch_folder``, T6 :class:`WatchedFolderWatcher`)
            # supplied them. Non-watched-folder callers pass ``None`` and
            # the frontmatter shape is unchanged from pre-T10.5.
            slug = self._slug_for(spec, title=summary.title)
            note_path, note_content = self._build_source_note(
                extracted=extracted,
                summary=summary,
                domain=domain,
                chash=chash,
                now=now,
                slug=slug,
                source_path=source_path,
                watched_folder_id=watched_folder_id,
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

    async def update_source(
        self,
        existing_note_path: Path,
        new_source_path: Path,
        *,
        allowed_domains: tuple[str, ...],
    ) -> IngestResult:
        """Re-ingest a single source against an existing vault note (Plan 22 T2).

        Preserves the note's slug + domain per D4 (no re-classify, no surprise
        domain move). Per D1 (source canonical / overwrite), the existing
        note's body + summary-derived sections are REPLACED on every
        content-changed update — hand-edits made to the vault note since the
        last ingest are LOST. Three branches:

        * ``new_hash == old_hash`` AND the resolved source path is unchanged
          → no-op. No LLM calls, no vault mutation. Emits a ``update |
          no_change | <slug>`` log entry for greppability.
        * ``new_hash == old_hash`` AND the source path changed → frontmatter-
          only mutation (``source_path`` + ``updated``). No LLM calls. Emits
          ``update | path_only | <slug>``.
        * ``new_hash != old_hash`` → full re-ingest (summarize + integrate),
          body + frontmatter rewritten in place via a single VaultWriter Edit
          (atomic temp+rename, undo record persisted, scope guard enforced).
          ``domain`` / ``created`` / ``watched_folder_id`` / ``source_url``
          frontmatter fields are PRESERVED. ``updated`` / ``content_hash`` /
          ``source_path`` are replaced. Emits ``update | overwrite | <slug>``.

        Stages skipped vs the 9-stage :meth:`ingest`:

        * **Stage 1 (classify)** — domain is read from existing frontmatter
          (D4). No classifier call, no `domain_override` semantics.
        * **Stage 4 (archive)** — re-archive only happens on overwrite (the
          no-op and path-only branches keep the existing archived copy).

        Args:
            existing_note_path: Absolute path to the vault note to update.
                Slug is preserved (derived from the path's stem).
            new_source_path: Path to the new source file on disk. May be the
                same path as the original ingest (typical "file edited"
                case) or a different path (the "file moved" case — same
                content_hash, different source_path).
            allowed_domains: Scope-guard tuple. The existing note's
                frontmatter ``domain`` MUST be in this tuple — otherwise
                the update is refused with a QUARANTINED result. Mirrors
                the :meth:`ingest` Stage 5 scope check.

        Returns:
            :class:`IngestResult` with status ``OK`` on success / no-op /
            path-only update. ``QUARANTINED`` when the note's domain is
            outside ``allowed_domains``. ``FAILED`` on any stage exception
            (mirrors :meth:`ingest`'s broad failure handler).
        """
        now = datetime.now(tz=UTC)
        run_cost: float = 0.0

        # Pre-compute slug from the existing path for early error paths
        # (FAILED log + record_failure). The actual slug used downstream is
        # the same value — preserved per D4.
        slug = existing_note_path.stem

        try:
            # Stage A: Scope-guard the existing note path. ``scope_guard``
            # also covers "the note must be inside the vault" — a caller
            # that hands us a stray path outside vault_root is rejected
            # before we read anything. ``include_orphans=True`` (Plan 22
            # T4) — :meth:`update_source` legitimately operates on
            # already-orphan notes when a watched source reappears, so
            # the default orphan filter must be bypassed at this seam.
            scope_guard(
                existing_note_path,
                vault_root=self.vault_root,
                allowed_domains=allowed_domains,
                include_orphans=True,
            )

            # Stage B: Read existing note's frontmatter + body. Failure here
            # (missing file, malformed YAML) flows to the FAILED branch.
            existing_content = existing_note_path.read_text(encoding="utf-8")
            existing_fm_dict, _existing_body = parse_frontmatter(existing_content)
            existing_fm = Frontmatter.from_dict(existing_fm_dict)

            # D4: domain is read from existing frontmatter. NEVER re-classify.
            existing_domain = existing_fm.domain
            if existing_domain is None:
                # Defensive: a note with no domain frontmatter cannot be
                # safely updated (we don't know which domain to bill the
                # cost against, and we don't know the integrate prompt's
                # index.md target). Treat as failure rather than QUARANTINED
                # (which is reserved for "classifier picked outside scope").
                raise ValueError(
                    f"existing note {existing_note_path} has no `domain` "
                    "frontmatter; cannot determine target domain for re-ingest"
                )

            # Scope check: the existing note's domain must be in allowed_domains.
            # Without this, a watcher scoped to ("research",) could overwrite a
            # personal-domain note that happens to share a slug.
            if existing_domain not in allowed_domains:
                error = (
                    f"existing note domain {existing_domain!r} "
                    f"not in allowed {allowed_domains}"
                )
                self._record_history(
                    source=str(new_source_path),
                    source_type=None,
                    domain=existing_domain,
                    status=IngestStatus.QUARANTINED.value,
                    patch_id=None,
                    error=error,
                    cost_usd=run_cost,
                )
                return IngestResult(
                    status=IngestStatus.QUARANTINED,
                    note_path=None,
                    errors=[error],
                )

            existing_hash = existing_fm.content_hash
            # ``source_path`` round-trips as a string through YAML — we
            # compare resolved paths (POSIX or platform-native form is fine
            # because both sides go through ``Path.resolve``).
            existing_source_path_str = existing_fm.source_path
            existing_source_path_resolved: Path | None = (
                Path(existing_source_path_str).resolve()
                if existing_source_path_str
                else None
            )

            # Stage C: Dispatch + extract (mirrors Stage 2-3 of ingest()).
            handler = await dispatch(new_source_path, handlers=self.handlers)
            archive_dir = archive_dir_for(
                vault_root=self.vault_root, domain=existing_domain, when=now
            )
            extracted = await handler.extract(new_source_path, archive_root=archive_dir)

            # Stage D: Hash + branch decision.
            new_hash = content_hash(extracted.body_text)
            new_source_resolved = new_source_path.resolve()
            path_changed = (
                existing_source_path_resolved is None
                or existing_source_path_resolved != new_source_resolved
            )
            hash_changed = existing_hash != new_hash

            if not hash_changed and not path_changed:
                # No-op branch: source content + path both unchanged.
                self._log_update(
                    domain=existing_domain,
                    op_summary=f"no_change | {slug}",
                )
                self._record_history(
                    source=str(new_source_path),
                    source_type=extracted.source_type.value,
                    domain=existing_domain,
                    status=IngestStatus.OK.value,
                    patch_id=None,
                    error=None,
                    cost_usd=run_cost,
                )
                return IngestResult(
                    status=IngestStatus.OK,
                    note_path=existing_note_path,
                    extracted=extracted,
                )

            if not hash_changed and path_changed:
                # Path-only branch: same body, source moved on disk.
                # Frontmatter ``source_path`` + ``updated`` get refreshed;
                # the body is unchanged. No LLM calls.
                new_content = self._rewrite_frontmatter_only(
                    existing_content=existing_content,
                    existing_fm_dict=existing_fm_dict,
                    new_source_path=new_source_resolved,
                    now=now,
                )
                receipt = self._apply_replacement(
                    note_path=existing_note_path,
                    domain=existing_domain,
                    old_content=existing_content,
                    new_content=new_content,
                )
                self._log_update(
                    domain=existing_domain,
                    op_summary=f"path_only | {slug}",
                )
                self._record_history(
                    source=str(new_source_path),
                    source_type=extracted.source_type.value,
                    domain=existing_domain,
                    status=IngestStatus.OK.value,
                    patch_id=receipt.undo_id,
                    error=None,
                    cost_usd=run_cost,
                )
                return IngestResult(
                    status=IngestStatus.OK,
                    note_path=existing_note_path,
                    extracted=extracted,
                )

            # Overwrite branch: content changed → run summarize + integrate.
            # Stage 1 (classify) is skipped per D4 — existing_domain is the
            # locked target. Stage 4 (archive) is implicitly covered above
            # since handler.extract() already wrote the new archive copy.
            summary, summarize_cost = await self._summarize(
                extracted, domain=existing_domain
            )
            run_cost += summarize_cost

            new_content = self._rebuild_note(
                existing_fm_dict=existing_fm_dict,
                extracted=extracted,
                summary=summary,
                new_source_path=new_source_resolved,
                new_hash=new_hash,
                now=now,
            )

            # Stage E: Integrate — exact same call as ingest(), feeds the LLM
            # the rendered new note body + the current index.md so it can
            # propose index/concept patches against the updated content.
            # NOTE: we intentionally DISCARD the integrate patch's
            # ``new_files`` and ``log_entry`` fields below — the file we
            # care about is the existing note, which is replaced via the
            # Edit (not a new_file), and the log entry uses the ``update``
            # verb we emit separately. ``edits`` + ``index_entries`` from
            # integrate ARE applied (they may add cross-domain index
            # entries for newly-mentioned entities/concepts).
            integrate_patch, integrate_cost = await self._integrate(
                extracted=extracted,
                summary=summary,
                domain=existing_domain,
                note_content=new_content,
            )
            run_cost += integrate_cost

            receipt = self._apply_replacement(
                note_path=existing_note_path,
                domain=existing_domain,
                old_content=existing_content,
                new_content=new_content,
                extra_edits=list(integrate_patch.edits),
                extra_index_entries=list(integrate_patch.index_entries),
            )
            self._log_update(
                domain=existing_domain,
                op_summary=f"overwrite | {slug}",
            )
            self._record_history(
                source=str(new_source_path),
                source_type=extracted.source_type.value,
                domain=existing_domain,
                status=IngestStatus.OK.value,
                patch_id=receipt.undo_id,
                error=None,
                cost_usd=run_cost,
            )
            return IngestResult(
                status=IngestStatus.OK,
                note_path=existing_note_path,
                extracted=extracted,
            )

        except ScopeError:
            # Scope violations bypass record_failure (they're a programmer/
            # caller error, not a pipeline failure) and propagate to the
            # caller. Callers (T6 watcher, T5 resync_folder tool) get a
            # clear PermissionError-shaped exception.
            raise
        except Exception as exc:
            record_failure(
                vault_root=self.vault_root,
                slug=slug,
                stage="update_source",
                exception=exc,
            )
            self._record_history(
                source=str(new_source_path),
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

    def mark_orphaned(
        self,
        existing_note_path: Path,
        *,
        allowed_domains: tuple[str, ...],
    ) -> IngestResult:
        """Mark a vault note as orphaned (Plan 22 T3, D2 non-destructive path).

        Flips the note's frontmatter to ``orphaned: true`` +
        ``orphaned_at: <today>``. The body is NOT modified — only two
        frontmatter fields change. The mutation goes through
        :class:`VaultWriter` (single Edit) so the change is atomic and
        recorded in the undo log: ``brain_undo_last`` reverts the note to
        its pre-mark frontmatter, including any prior ``orphaned: false``
        or absent ``orphaned`` field.

        Two branches:

        * **mark** — note's current frontmatter has ``orphaned: false`` (or
          the field is absent). Frontmatter flipped, vault written, undo
          record persisted, log entry ``orphan | mark | <slug>``.
        * **no_change** — note is ALREADY ``orphaned: true``. Idempotent:
          no vault write, no LLM call, ``orphaned_at`` preserved (so the
          original orphan-mark timestamp survives a re-call). Log entry
          ``orphan | no_change | <slug>`` is still emitted for greppability.

        Called by D7's symmetric watcher on ``FileDeletedEvent`` and by
        T5's ``brain_resync_folder`` when a tracked file has disappeared
        from disk. Never deletes the note itself — D2 keeps adjudication
        manual (the user picks delete via ``brain_delete_orphan`` after
        :meth:`mark_orphaned` has run).

        Args:
            existing_note_path: Absolute path to the vault note to mark.
                Slug is derived from the stem for log greppability.
            allowed_domains: Scope-guard tuple. The note's frontmatter
                ``domain`` MUST be in this tuple — a watcher scoped to
                ``("research",)`` cannot accidentally orphan a personal-
                domain note. ``scope_guard`` enforces the path side; the
                domain check below enforces the frontmatter side.

        Returns:
            :class:`IngestResult` with status ``OK`` on success / no-op.
            ``QUARANTINED`` when the note's domain is outside
            ``allowed_domains``. ``FAILED`` on any stage exception
            (missing file, malformed frontmatter, etc.). Mirrors
            :meth:`update_source`'s failure shape so callers can branch
            on status uniformly.

        Raises:
            ScopeError: The note path is outside ``vault_root`` or
                outside ``allowed_domains``. Propagates so callers (T6
                watcher, T5 resync tool) see a clear ``PermissionError``-
                shaped exception, matching :meth:`update_source` Stage A.
        """
        now = datetime.now(tz=UTC)
        slug = existing_note_path.stem

        try:
            # Stage A: scope-guard the path. Mirrors update_source — also
            # covers "must be inside vault_root". ``include_orphans=True``
            # (Plan 22 T4) — :meth:`mark_orphaned` is idempotent and may
            # be re-called against an already-orphan note (Stage D below
            # short-circuits to the no-op log line). The default orphan
            # filter would block that idempotency path, so opt out here.
            scope_guard(
                existing_note_path,
                vault_root=self.vault_root,
                allowed_domains=allowed_domains,
                include_orphans=True,
            )

            # Stage B: read existing note. ``read_text`` raises
            # FileNotFoundError when the path doesn't exist — that flows
            # to the FAILED branch below, matching update_source's
            # error-handling shape.
            existing_content = existing_note_path.read_text(encoding="utf-8")
            existing_fm_dict, _existing_body = parse_frontmatter(existing_content)
            existing_fm = Frontmatter.from_dict(existing_fm_dict)

            existing_domain = existing_fm.domain
            if existing_domain is None:
                # Defensive: a note with no domain frontmatter cannot be
                # safely orphaned. We don't know which domain's log.md to
                # append to, and a scope check against a missing domain
                # would be meaningless. Treat as FAILED rather than
                # QUARANTINED (which is reserved for "domain known but
                # outside scope").
                raise ValueError(
                    f"existing note {existing_note_path} has no `domain` "
                    "frontmatter; cannot determine target domain for orphan-mark"
                )

            # Stage C: scope check the note's domain. Without this, a
            # watcher scoped to ``("research",)`` could orphan a personal-
            # domain note that lives at a path scope_guard happens to
            # accept (e.g. a hypothetical cross-domain symlink). Belt-and-
            # braces.
            if existing_domain not in allowed_domains:
                error = (
                    f"existing note domain {existing_domain!r} "
                    f"not in allowed {allowed_domains}"
                )
                return IngestResult(
                    status=IngestStatus.QUARANTINED,
                    note_path=None,
                    errors=[error],
                )

            # Stage D: idempotency check. ``Frontmatter.orphaned`` defaults
            # to ``False`` so a missing field reads as ``False`` and we
            # proceed to the mark branch. Only an explicit ``orphaned:
            # true`` short-circuits.
            if existing_fm.orphaned:
                # Idempotent no-op: preserve the original orphaned_at
                # timestamp (audit) and emit a greppable log line.
                self._log_orphan(
                    domain=existing_domain,
                    op_summary=f"no_change | {slug}",
                )
                return IngestResult(
                    status=IngestStatus.OK,
                    note_path=existing_note_path,
                )

            # Stage E: rewrite frontmatter (body unchanged) and apply
            # atomically via VaultWriter. The single Edit lands an undo
            # record that ``brain_undo_last`` can revert — flipping the
            # note back to its pre-mark frontmatter (``orphaned: false``
            # or absent, depending on what was there before).
            new_content = self._rewrite_frontmatter_for_orphan(
                existing_content=existing_content,
                existing_fm_dict=existing_fm_dict,
                now=now,
            )
            self._apply_replacement(
                note_path=existing_note_path,
                domain=existing_domain,
                old_content=existing_content,
                new_content=new_content,
            )
            self._log_orphan(
                domain=existing_domain,
                op_summary=f"mark | {slug}",
            )
            return IngestResult(
                status=IngestStatus.OK,
                note_path=existing_note_path,
            )

        except ScopeError:
            # Scope violations bypass record_failure (programmer / caller
            # error, not a pipeline failure) and propagate — same shape
            # as update_source so T5 / T6 callers can match on it
            # uniformly.
            raise
        except Exception as exc:
            record_failure(
                vault_root=self.vault_root,
                slug=slug,
                stage="mark_orphaned",
                exception=exc,
            )
            return IngestResult(
                status=IngestStatus.FAILED,
                note_path=None,
                errors=[str(exc)],
            )

    def _rewrite_frontmatter_only(
        self,
        *,
        existing_content: str,
        existing_fm_dict: dict[str, object],
        new_source_path: Path,
        now: datetime,
    ) -> str:
        """Rewrite the note with new ``source_path`` + ``updated`` only.

        Preserves the body verbatim — used by the path-only branch
        (content_hash unchanged, source file moved). Returns the full
        serialized note content (frontmatter + body).
        """
        new_fm = dict(existing_fm_dict)
        new_fm["updated"] = now.date().isoformat()
        new_fm["source_path"] = str(new_source_path)
        # Re-parse body so we serialize cleanly with the same body bytes
        # that were on disk.
        _fm, body = parse_frontmatter(existing_content)
        return serialize_with_frontmatter(new_fm, body=body)

    def _rewrite_frontmatter_for_orphan(
        self,
        *,
        existing_content: str,
        existing_fm_dict: dict[str, object],
        now: datetime,
    ) -> str:
        """Rewrite the note flipping ``orphaned: true`` + ``orphaned_at: <today>``.

        Preserves the body verbatim — only frontmatter fields change. Used
        by :meth:`mark_orphaned` (Plan 22 T3). Returns the full serialized
        note content (frontmatter + body). All other frontmatter keys
        (including user-added extras like ``aliases`` / ``cssclass``)
        round-trip unchanged.
        """
        new_fm = dict(existing_fm_dict)
        new_fm["orphaned"] = True
        new_fm["orphaned_at"] = now.date().isoformat()
        _fm, body = parse_frontmatter(existing_content)
        return serialize_with_frontmatter(new_fm, body=body)

    def _rebuild_note(
        self,
        *,
        existing_fm_dict: dict[str, object],
        extracted: ExtractedSource,
        summary: SummarizeOutput,
        new_source_path: Path,
        new_hash: str,
        now: datetime,
    ) -> str:
        """Rebuild the note content for the overwrite branch.

        Frontmatter fields preserved from the existing note: ``domain``,
        ``type``, ``created``, ``watched_folder_id``, plus any user-added
        keys (``aliases``, ``cssclass``, etc.). Frontmatter fields
        replaced: ``title`` (from new summary), ``updated``, ``source_type``,
        ``source_url``, ``content_hash``, ``ingested_by``, ``source_path``.

        ``orphaned`` is set to ``False`` and ``orphaned_at`` is cleared:
        a successful re-ingest is implicit evidence the source is back on
        disk, so any prior orphan-mark is reverted. (Pinned in tests; T3
        will set them when the source disappears.)
        """
        # Start from the existing dict so user-added extras survive.
        new_fm: dict[str, object] = dict(existing_fm_dict)
        # Title comes from the new summary — overwrite contract per D1.
        new_fm["title"] = summary.title
        # Re-stamp `updated` to today. `created` is preserved.
        new_fm["updated"] = now.date().isoformat()
        new_fm["source_type"] = extracted.source_type.value
        new_fm["source_url"] = extracted.source_url
        new_fm["content_hash"] = new_hash
        new_fm["ingested_by"] = "brain"
        new_fm["source_path"] = str(new_source_path)
        # A successful re-ingest implies the source is back; clear any
        # prior orphan-mark. T3 will write the inverse transition.
        new_fm["orphaned"] = False
        new_fm["orphaned_at"] = None
        body = _render_source_body(summary=summary)
        return serialize_with_frontmatter(new_fm, body=body)

    def _apply_replacement(
        self,
        *,
        note_path: Path,
        domain: str,
        old_content: str,
        new_content: str,
        extra_edits: list[Edit] | None = None,
        extra_index_entries: list[IndexEntryPatch] | None = None,
    ) -> Receipt:
        """Atomically replace ``note_path`` content via ``VaultWriter``.

        Builds a PatchSet with a single Edit (old=full prior content,
        new=full new content). Optional ``extra_edits`` / ``extra_index_entries``
        are appended so the integrate stage's cross-domain index/entity
        patches land in the same atomic write + undo record. ``log_entry``
        on the PatchSet is left ``None`` — the caller emits the ``update``-
        verb log entry separately via :meth:`_log_update` so the log
        captures the correct verb (the writer would otherwise stamp
        ``op="patch"``).

        ``include_orphans=True`` is passed to :meth:`VaultWriter.apply`
        (Plan 22 T4). This helper is shared by :meth:`update_source`
        (clears orphan mark on successful re-ingest — the target note
        may already be ``orphaned: true``) and :meth:`mark_orphaned`
        (target is by definition about to BE marked orphan, and may
        already be — Stage E only runs on the non-idempotent branch).
        Both contexts legitimately operate on orphan notes; the default
        scope_guard filter would block them.
        """
        edits: list[Edit] = [
            Edit(path=note_path, old=old_content, new=new_content),
        ]
        if extra_edits:
            edits.extend(extra_edits)
        idx_entries: list[IndexEntryPatch] = list(extra_index_entries or [])
        patch = PatchSet(
            new_files=[],
            edits=edits,
            index_entries=idx_entries,
            log_entry=None,  # logged separately with op="update"
            reason="update_source",
        )
        return self.writer.apply(patch, allowed_domains=(domain,), include_orphans=True)

    def _log_update(self, *, domain: str, op_summary: str) -> None:
        """Append a single ``update``-verb entry to the domain's ``log.md``.

        Uses :class:`LogFile` directly (the same surface ``VaultWriter``
        uses internally) so we can stamp ``op="update"`` — the writer's
        :meth:`apply` hardcodes ``op="patch"`` for PatchSet log entries.
        Greppable per the Plan 22 T2 review criterion (c).
        """
        log_path = self.vault_root / domain / "log.md"
        log = LogFile(log_path)
        log.append(
            LogEntry(
                timestamp=datetime.now(tz=UTC),
                op="update",
                summary=op_summary,
            )
        )

    def _log_orphan(self, *, domain: str, op_summary: str) -> None:
        """Append a single ``orphan``-verb entry to the domain's ``log.md``.

        Mirrors :meth:`_log_update` but stamps ``op="orphan"``. Used by
        :meth:`mark_orphaned` (Plan 22 T3) so the orphan-mark transition
        and the idempotent no-op re-mark are both greppable distinctly
        from the ``patch`` / ``update`` verbs.
        """
        log_path = self.vault_root / domain / "log.md"
        log = LogFile(log_path)
        log.append(
            LogEntry(
                timestamp=datetime.now(tz=UTC),
                op="orphan",
                summary=op_summary,
            )
        )

    async def _classify_with_cost(
        self,
        *,
        title: str,
        snippet: str,
        allowed_domains: tuple[str, ...],
        domain: str | None = None,
    ) -> tuple[ClassifyResult, float]:
        """Run the classify prompt inline and return (result, cost_usd).

        Pipeline-private variant of :func:`brain_core.ingest.classifier.classify`
        — keeps the public free function unchanged for other callers
        (BulkImporter, the standalone classify tool, contract tests) while
        giving the pipeline access to the response usage so it can charge
        the spend to ``ingest_history.cost_usd`` (issue #29).

        Plan 10 Task 4 plumbs the call's ``allowed_domains`` through to
        :meth:`Prompt.render_system` so the prompt's enum (D6/D8) lists
        exactly the user's currently-active scope. The reply is parsed
        permissively — the pipeline's existing
        ``if domain not in allowed_domains`` check (Stage 5) routes
        out-of-set replies to QUARANTINED, preserving the v0.1 behavior.
        """
        prompt = load_prompt("classify")
        domains_text = ", ".join(f"`{d}`" for d in allowed_domains)
        system = prompt.render_system(domains=domains_text)
        user_content = prompt.render(title=title, snippet=snippet)
        # Plan 16 Task 28.5: per-domain budget guard fires BEFORE the LLM
        # round-trip. ``domain`` here is ``domain_override`` (when supplied)
        # — the auto-detect path passes ``None`` and the guard no-ops,
        # which is the correct shape: we cannot enforce a per-domain cap
        # against an unknown domain (the very call we're about to make is
        # what classifies it).
        if self.guard is not None:
            self.guard.check_for(domain=domain, config=self.config)
        response = await self.llm.complete(
            LLMRequest(
                model=self.classify_model,
                system=system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=256,
                temperature=0.0,
                # Plan 16 Task 31.5: thread ``domain_override`` (or
                # ``None`` on auto-detect) into the request so the
                # AnthropicProvider's per-domain rate-limit gate (T31)
                # can fire. Auto-detect path passes ``None`` and the
                # gate no-ops — same shape as the budget guard above.
                domain=domain,
            )
        )
        parsed = json.loads(response.content)
        out = ClassifyOutput.model_validate(parsed)
        result = ClassifyResult(
            source_type=out.source_type,
            domain=out.domain,
            confidence=out.confidence,
            needs_user_pick=out.confidence < 0.7,
        )
        return result, _estimate_call_cost(self.classify_model, response)

    async def _ocr_images(
        self,
        extracted: ExtractedSource,
        *,
        domain: str,
    ) -> ExtractedSource:
        """Run Claude Vision OCR on every image in ``extracted.extras["images"]``
        and inline the recovered text into ``body_text``.

        Plan 24 Task 4. Behavior:

        * No-op when ``extras["images"]`` is missing / empty.
        * No-op when ``self.guard`` / ``self.config`` / ``self.cost_ledger``
          is ``None`` — OCR requires the per-domain budget gate + the
          cost ledger, and missing rails would silently bypass them.
        * Per-image error handling:
            - :class:`BudgetCapExceeded` — re-raised. Budget exhaustion
              mid-OCR aborts the entire ingest; the outer ``try`` in
              :meth:`ingest` records the failure (status=FAILED).
            - Any other exception (LLM error, malformed image, etc.) —
              logged + skipped. Remaining images still get OCR'd.
            - Empty OCR text — no inline block is emitted (avoids
              ``[Image: ]`` noise in the body).
        * Inline format:
            - ``[Image (slide N): <text>]`` when the image dict carries
              ``slide_index`` (PptxHandler).
            - ``[Image: <text>]`` otherwise (DocxHandler and any future
              non-slide-positioned handler).
        * OCR blocks are APPENDED to the end of ``body_text`` with a
          double-newline separator. Per-slide interleaving (inserting
          the block after the matching ``## Slide N`` section) is
          deferred — the slide-index marker in the inline block gives
          downstream LLM prompts enough context.

        Returns a new :class:`ExtractedSource` (the dataclass is frozen)
        with the augmented ``body_text``; ``extras`` is preserved
        verbatim so downstream consumers can still see the original image
        list.
        """
        images: list[dict[str, Any]] = (
            extracted.extras.get("images", []) if extracted.extras else []
        )
        if not images:
            return extracted
        if self.guard is None or self.config is None or self.cost_ledger is None:
            # Missing OCR rails. We don't want to call the LLM without a
            # budget gate or the ability to record a ledger row, so skip.
            # Log so the operator can spot the misconfiguration in stderr
            # / log file (e.g. CLI ingest without ``--config``).
            _log.info(
                "ingest.ocr.skipped_no_rails",
                image_count=len(images),
                has_guard=self.guard is not None,
                has_config=self.config is not None,
                has_cost_ledger=self.cost_ledger is not None,
            )
            return extracted

        ocr_blocks: list[str] = []
        for img in images:
            try:
                result = await ocr_image(
                    image_bytes=img["blob"],
                    content_type=img.get("content_type", "image/png"),
                    domain=domain,
                    llm_provider=self.llm,
                    cost_ledger=self.cost_ledger,
                    budget_guard=self.guard,
                    config=self.config,
                )
            except BudgetCapExceeded:
                # Per plan-doc §T4 step 5: re-raise so the outer ingest
                # ``try`` catches it and records a FAILED row. Partial
                # OCR work already done in this pass is preserved on the
                # ledger (each ``ocr_image`` call records its row before
                # returning), but no inline blocks land in body_text —
                # the FAILED ingest doesn't produce a vault note anyway.
                raise
            except Exception as exc:
                _log.warning(
                    "ingest.ocr.image_skipped",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    image_index=img.get("index"),
                    slide_index=img.get("slide_index"),
                )
                continue

            text = result.text.strip()
            if not text:
                # Empty OCR → don't emit an empty ``[Image: ]`` block.
                continue

            slide_index = img.get("slide_index")
            if slide_index is not None:
                ocr_blocks.append(f"[Image (slide {slide_index}): {text}]")
            else:
                ocr_blocks.append(f"[Image: {text}]")

        if not ocr_blocks:
            return extracted

        suffix = "\n\n".join(ocr_blocks)
        new_body = (
            f"{extracted.body_text}\n\n{suffix}" if extracted.body_text else suffix
        )
        return replace(extracted, body_text=new_body)

    async def _summarize(
        self,
        extracted: ExtractedSource,
        *,
        domain: str,
    ) -> tuple[SummarizeOutput, float]:
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
        # Plan 16 Task 28.5: per-domain budget guard fires BEFORE the LLM
        # round-trip. ``domain`` is the resolved post-classify domain.
        if self.guard is not None:
            self.guard.check_for(domain=domain, config=self.config)
        response = await self.llm.complete(
            LLMRequest(
                model=self.summarize_model,
                system=prompt.system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=2048,
                temperature=0.2,
                # Plan 16 Task 31.5: thread the resolved post-classify
                # domain into the request so the AnthropicProvider's
                # per-domain rate-limit gate (T31) can fire.
                domain=domain,
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
        # Plan 16 Task 28.5: per-domain budget guard fires BEFORE the LLM
        # round-trip. ``domain`` is the resolved post-classify domain.
        if self.guard is not None:
            self.guard.check_for(domain=domain, config=self.config)
        response = await self.llm.complete(
            LLMRequest(
                model=self.integrate_model,
                system=prompt.system,
                messages=[LLMMessage(role="user", content=user_content)],
                max_tokens=2048,
                temperature=0.2,
                # Plan 16 Task 31.5: thread the resolved post-classify
                # domain into the request so the AnthropicProvider's
                # per-domain rate-limit gate (T31) can fire.
                domain=domain,
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

    def _quarantine_content_sniff(
        self,
        *,
        spec: str | Path,
        slug: str,
        extracted: ExtractedSource,
    ) -> Path:
        """Write a Stage 3.5 content-sniff quarantine record (Plan 25 T2 / D4).

        Path layout: ``<vault_root>/raw/inbox/failed/<slug>.<ts>.needs_review.json``.
        The compact UTC timestamp suffix mirrors :func:`record_failure`'s retry-
        history behavior — re-ingesting the same source after a quarantine
        keeps prior records.

        JSON shape captures the diagnostic counts the sniff helper used so
        the user can audit the rejection in the Inbox UI:

        * ``stage`` — always ``"content_sniff"``.
        * ``reason`` — always ``"non_meaningful_text"``.
        * ``source_path`` — string form of ``spec``.
        * ``source_type`` — the resolved :class:`SourceType` value.
        * ``slug`` — preliminary slug used for the path.
        * ``ts_utc`` — ISO 8601 UTC timestamp.
        * ``details.char_count`` — length of ``extracted.body_text``.
        * ``details.printable_ratio`` — printable / total (0.0 on empty body).
        * ``details.letter_ratio`` — alpha / total (0.0 on empty body).
        * ``details.has_ocr_markers`` — whether D15 OCR-marker exception was
          relevant (True + still-rejected pins the "OCR marker is not a
          binary-content bypass" contract).
        * ``retry_hint`` — plain-English next-action string.

        Returns the path of the written record (mirrors :func:`record_failure`
        so the caller and tests can locate the artefact).
        """
        now = datetime.now(tz=UTC)
        failed_dir = self.vault_root / "raw" / "inbox" / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        ts_compact = now.strftime("%Y%m%dT%H%M%S%f")
        path = failed_dir / f"{slug}.{ts_compact}.needs_review.json"

        body = extracted.body_text
        body_len = len(body)
        if body_len > 0:
            printable_ratio = sum(1 for c in body if c.isprintable()) / body_len
            letter_ratio = sum(1 for c in body if c.isalpha()) / body_len
        else:
            printable_ratio = 0.0
            letter_ratio = 0.0
        has_ocr_markers = bool(_OCR_MARKER_PATTERN.search(body))

        record = {
            "stage": "content_sniff",
            "reason": "non_meaningful_text",
            "source_path": str(spec),
            "source_type": extracted.source_type.value,
            "slug": slug,
            "ts_utc": now.isoformat(),
            "details": {
                "char_count": body_len,
                "printable_ratio": printable_ratio,
                "letter_ratio": letter_ratio,
                "has_ocr_markers": has_ocr_markers,
            },
            "retry_hint": (
                "If you believe this file is meaningful, classify it manually "
                "via the Inbox UI or re-ingest with a different handler."
            ),
        }
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return path

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
        source_path: Path | None = None,
        watched_folder_id: str | None = None,
    ) -> tuple[Path, str]:
        """Build the canonical source note: frontmatter + structured markdown body.

        Returns `(note_path, note_content)`. `note_path` is
        `<vault_root>/<domain>/sources/<slug>.md`.

        Frontmatter fields written:
            title, domain, type=source, created, updated, source_type,
            source_url, content_hash, ingested_by
            (+ ``source_path`` when ``source_path`` is not None — Plan 22 T10.5)
            (+ ``watched_folder_id`` when ``watched_folder_id`` is not None
             — Plan 22 T10.5)

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

        Plan 22 T10.5 contract: when ``source_path`` is set, the resulting
        note's frontmatter carries the resolved absolute-path string
        (``str(source_path.resolve())``), mirroring T2's :meth:`update_source`
        convention. When ``watched_folder_id`` is set, the frontmatter
        carries that string verbatim. These are the two fields T6's
        :func:`_index_vault_for_folder` filters on to map a source-path
        event back to its vault note — without them, the watcher's modify
        path falls through to :meth:`ingest` (creating a duplicate) and
        delete events silently no-op.
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
        # Plan 22 T10.5: thread the watched-context fields when provided.
        # We omit the keys entirely when the kwargs are ``None`` so that
        # serialized YAML for non-watched-folder ingests stays byte-identical
        # to the pre-T10.5 shape (`Frontmatter.from_dict` reads a missing
        # key as ``None`` anyway, so the consumer contract is unchanged).
        if source_path is not None:
            try:
                fm["source_path"] = str(source_path.resolve())
            except OSError:
                # ``resolve()`` can raise on a permission-denied parent on
                # some platforms. Fall back to the raw path string — the
                # downstream consumer (T6 watcher) does its own
                # ``.resolve()`` on lookup so an unresolved value is
                # tolerated.
                fm["source_path"] = str(source_path)
        if watched_folder_id is not None:
            fm["watched_folder_id"] = watched_folder_id
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
