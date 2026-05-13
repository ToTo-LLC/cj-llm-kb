"""BulkImporter — folder-level dry-run / apply wrapper around IngestPipeline.

Workflow:
  1. Call `plan(folder, ...)` to walk the folder, run the classifier (or skip if
     domain_override is set), and build a BulkPlan without touching the vault.
  2. Inspect the plan (print it, present it to the user, etc.).
  3. Call `apply(plan, ...)` to run the full IngestPipeline per item and return
     a list of IngestResult in the same order as plan.items.

Plan 26 T3 adds :meth:`BulkImporter.plan_streaming` — an async generator
yielding :class:`brain_core.ingest.walk_events.WalkEvent` instances so
brain_api can serve real walk-phase progress to the bulk-import wizard
over Server-Sent Events. The streaming path does NOT touch the
classifier and does NOT return a :class:`BulkPlan`; it exists purely
for UI progress. The wizard still calls :meth:`plan` separately to get
the actual planned items (D-decision (a) in Plan 26).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from brain_core.ingest.classifier import classify
from brain_core.ingest.dispatcher import DispatchError, dispatch
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestResult
from brain_core.ingest.walk_events import (
    WalkComplete,
    WalkError,
    WalkEvent,
    WalkProgress,
    WalkStarted,
)

# Plan 26 T3 D9: emit a WalkProgress event every N candidate files seen
# during the walk. Cuts SSE chatter to ~one frame per 50ms even on a
# fast SSD walk over 10k files (vs ~one per ms if we emitted per file).
_WALK_PROGRESS_INTERVAL: int = 50


@dataclass(frozen=True)
class BulkItem:
    """One planned ingest. Populated during `plan(...)`, consumed by `apply(...)`."""

    spec: Path
    slug: str  # preliminary slug from IngestPipeline._slug_for
    classified_domain: str | None  # None if dry-run skipped classify (domain_override path)
    confidence: float | None  # None if no classify call was made
    # Plan 07 Task 4: idempotency hint surfaced from the dry-run.
    # ``True`` iff the file's content_hash already matches a source note
    # under one of ``allowed_domains`` — applying it would no-op via the
    # pipeline's stage-4 SKIPPED_DUPLICATE branch. The frontend uses this
    # to render the bulk-import dry-run table's "dup" warn-chip.
    duplicate: bool = False


@dataclass
class BulkPlan:
    items: list[BulkItem] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)  # e.g. unsupported file types, hidden files

    def __len__(self) -> int:
        return len(self.items)


def _is_hidden(path: Path, *, root: Path) -> bool:
    """Return True if `path` or any ancestor component up to `root` starts with '.'."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


# Plan 25 T1: cross-platform system-file denylist. Catches OS-generated
# files (Mac/Windows/Linux) and dev-artifact directories that are never
# user content. `_is_hidden` already covers dotfiles like `.git/`,
# `.DS_Store`, `.idea/` — entries below that DO start with `.` are
# belt-and-suspenders, but the non-dot entries (`Thumbs.db`, `Desktop.ini`,
# `$RECYCLE.BIN/`, `__MACOSX/`, etc.) are the load-bearing ones since
# `_is_hidden` cannot catch them.
_SYSTEM_FILES: frozenset[str] = frozenset(
    {
        # Mac
        ".DS_Store",
        "__MACOSX",
        ".Spotlight-V100",
        ".fseventsd",
        ".Trashes",
        ".DocumentRevisions-V100",
        ".TemporaryItems",
        ".AppleDouble",
        ".AppleDB",
        ".AppleDesktop",
        ".LSOverride",
        ".VolumeIcon.icns",
        ".com.apple.timemachine.donotpresent",
        "Icon\r",  # Mac folder custom icon
        "Network Trash Folder",
        # Windows
        "Thumbs.db",
        "ehthumbs.db",
        "ehthumbs_vista.db",
        "Desktop.ini",
        "desktop.ini",
        "$RECYCLE.BIN",
        "System Volume Information",
        "pagefile.sys",
        "hiberfil.sys",
        "swapfile.sys",
        # Linux
        ".directory",
        # Dev artifacts (often misplaced in a bulk-import folder; not
        # strictly OS-system but never user knowledge-base content).
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".idea",
        ".vscode",
    }
)


# Plan 25 T1: whitelist of file extensions claimable by a registered
# handler when walking a folder. Derived from each handler's
# ``can_handle`` suffix check:
#   - TextHandler              → .txt, .md, .markdown
#   - PDFHandler               → .pdf
#   - TranscriptVTTHandler     → .vtt, .srt
#   - DocxHandler              → .docx
#   - TranscriptDOCXHandler    → .docx (content-sniffed)
#   - PptxHandler              → .pptx
#   - EmailHandler             → str only (pasted .eml); .eml files
#                                 on disk currently fall through to
#                                 the dispatcher with no claimer, but
#                                 .eml is included for forward-compat
#                                 with a future path-based handler.
#   - URLHandler / TweetHandler → str only (URLs); not applicable to
#                                 folder walks.
_VALID_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".pdf",
        ".eml",
        ".vtt",
        ".srt",
        ".docx",
        ".pptx",
    }
)


def _is_system_file(name: str) -> bool:
    """Return True if ``name`` matches a system-file denylist entry.

    Handles both exact-name matches against the cross-platform
    ``_SYSTEM_FILES`` set and pattern-based matches:

    - ``._*`` — AppleDouble files (e.g. ``._image.png``)
    - ``.Trash-*`` — Linux trash folders (e.g. ``.Trash-1000``)
    - ``~$*`` — Office temp files (e.g. ``~$document.docx``)
    """
    if name in _SYSTEM_FILES:
        return True
    if name.startswith("._"):  # AppleDouble
        return True
    if name.startswith(".Trash-"):  # Linux trash
        return True
    if name.startswith("~$"):  # Office temp
        return True
    return False


class BulkImporter:
    """Thin wrapper around IngestPipeline for folder-level operations."""

    def __init__(self, pipeline: IngestPipeline) -> None:
        self._pipeline = pipeline

    async def plan(
        self,
        folder: Path,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
        glob: str = "**/*",
        max_files: int | None = None,
    ) -> BulkPlan:
        """Walk `folder` and build a BulkPlan.

        For each file:
        - Skip hidden files (any path component starting with '.').
        - Skip directories and symlinks.
        - Skip files the dispatcher doesn't claim (add to `skipped`).
        - If `domain_override` is set: do NOT call the classifier.
          classified_domain is the override, confidence is None.
        - Else: call the classifier with the file's first 1000 bytes as the
          snippet (UTF-8 best-effort, errors="replace"). If the classifier
          returns a domain NOT in `allowed_domains`, still include the item in
          the plan — the caller can choose to skip/reroute. Quarantine check
          happens at `apply` time.

        ``max_files`` (issue #28) caps the number of items that end up in the
        plan. The walk short-circuits once the cap is reached, so the
        classifier is not called on files that would have been truncated
        anyway — the MCP/CLI layer used to pass an unbounded plan and slice
        post-classify, wasting classifier tokens on the overflow.

        Does NOT write to the vault. Does NOT call summarize or integrate.
        """
        if max_files is not None and max_files <= 0:
            raise ValueError(f"max_files must be positive, got {max_files}")

        result = BulkPlan()

        for p in sorted(folder.glob(glob)):
            # Stop walking as soon as we hit the planned-item cap. We check
            # at the TOP of the loop so the cap is evaluated before any
            # per-file work (handler probe, hashing, classify) — that's
            # the whole point of the kwarg.
            if max_files is not None and len(result.items) >= max_files:
                break
            # Skip non-files and symlinks
            if not p.is_file() or p.is_symlink():
                continue

            # Skip hidden files / paths
            if _is_hidden(p, root=folder):
                continue

            # Plan 25 T1: system-file denylist — catches non-dot system
            # files like Thumbs.db, Desktop.ini, $RECYCLE.BIN/, __MACOSX/,
            # and pattern-based matches (`._*`, `.Trash-*`, `~$*`). These
            # are silently filtered, NOT added to `skipped` — the user
            # never wants to see OS clutter in the plan view.
            if _is_system_file(p.name):
                continue
            # Plan 25 T1: also drop any file whose ancestor path contains
            # a system directory (e.g. a file deep inside __MACOSX/ must
            # be excluded even if its own filename is not a system match).
            if any(_is_system_file(part) for part in p.relative_to(folder).parts):
                continue
            # Plan 25 T1: unsupported-type pre-filter — only files with
            # extensions claimable by a registered handler enter the plan.
            # Video/archive/executable/image and other non-text formats
            # are silently walked over and DO NOT appear in `skipped`.
            if p.suffix.lower() not in _VALID_EXTENSIONS:
                continue

            # Check that a handler claims this file. Reuse the pipeline's
            # handler list (issue #23) so config-supplied tunables take
            # effect for the bulk path too.
            try:
                await dispatch(p, handlers=self._pipeline.handlers)
            except DispatchError:
                result.skipped.append(p)
                continue

            # Build the BulkItem
            slug = self._pipeline._slug_for(p)

            # Compute the duplicate flag. Use the file's full bytes (decoded
            # best-effort) hashed via the same ``content_hash`` helper the
            # pipeline uses inside ``ingest()`` Stage 4 — keeps the dry-run's
            # dup detection consistent with the apply path. Skip on read
            # failure (the file is also probably going to fail apply, but
            # that's a separate signal we don't override here).
            duplicate = False
            try:
                file_bytes = p.read_bytes()
                file_text = file_bytes.decode("utf-8", errors="replace")
                chash = content_hash(file_text)
                duplicate = self._pipeline._already_ingested(chash, allowed_domains)
            except OSError:
                pass

            if domain_override is not None:
                item = BulkItem(
                    spec=p,
                    slug=slug,
                    classified_domain=domain_override,
                    confidence=None,
                    duplicate=duplicate,
                )
            else:
                # Read up to 1000 bytes and decode best-effort
                with p.open("rb") as fh:
                    raw = fh.read(1000)
                snippet = raw.decode("utf-8", errors="replace")

                cls = await classify(
                    llm=self._pipeline.llm,
                    model=self._pipeline.classify_model,
                    title=p.stem,
                    snippet=snippet,
                    allowed_domains=allowed_domains,
                )
                item = BulkItem(
                    spec=p,
                    slug=slug,
                    classified_domain=cls.domain,
                    confidence=cls.confidence,
                    duplicate=duplicate,
                )

            result.items.append(item)

        return result

    async def apply(
        self,
        plan: BulkPlan,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
        watched_folder_id: str | None = None,
    ) -> list[IngestResult]:
        """Run `IngestPipeline.ingest` for each item in the plan, in order.

        Per-item domain selection precedence:
          1. Caller's global ``domain_override`` (forces every item into one domain).
          2. The item's own ``classified_domain`` from the plan phase
             (honors the per-item classification the plan already paid for).
          3. ``None`` — pipeline re-classifies fresh.

        Honoring (2) is the whole reason the plan phase exists: without it the
        classifier work done during ``plan()`` is thrown away and every item
        gets re-classified inside ``ingest()``.

        Plan 22 T10.5: when ``watched_folder_id`` is provided, every per-item
        ``pipeline.ingest`` call receives BOTH the per-item ``source_path``
        (derived from ``item.spec``, which is always a local file path —
        the dispatcher gate runs at :meth:`plan` time) AND the shared
        ``watched_folder_id``. The resulting source notes therefore carry
        the frontmatter fields T6's :class:`WatchedFolderWatcher` lookup
        depends on. When ``watched_folder_id`` is ``None`` (the default,
        for bulk-import without watch context — drag-drop, the standalone
        ``brain_bulk_import`` tool), no ``source_path`` is threaded either:
        non-watched-folder bulk imports remain spec-clean per
        :class:`brain_core.vault.frontmatter.Frontmatter` (the field is
        defined as "only set when ingestion came from a local file" — bulk
        imports DO satisfy that, but absent a watched-folder linkage we
        preserve the pre-T10.5 shape to avoid surfacing the path on notes
        that have no folder to link back to). A future plan can flip this
        if bulk-import-only ``source_path`` becomes useful.

        Returns a list of IngestResult in the same order as plan.items. Does
        NOT short-circuit on FAILED items — each item is independent.
        """
        results: list[IngestResult] = []
        for item in plan.items:
            effective_override = domain_override or item.classified_domain
            # Plan 22 T10.5: thread the per-item source path AND the shared
            # watched_folder_id ONLY when the caller signaled a watched-
            # folder context (watched_folder_id is not None). This keeps
            # non-watched-folder bulk imports byte-identical to pre-T10.5
            # frontmatter shape.
            if watched_folder_id is not None:
                result = await self._pipeline.ingest(
                    item.spec,
                    allowed_domains=allowed_domains,
                    domain_override=effective_override,
                    source_path=item.spec,
                    watched_folder_id=watched_folder_id,
                )
            else:
                result = await self._pipeline.ingest(
                    item.spec,
                    allowed_domains=allowed_domains,
                    domain_override=effective_override,
                )
            results.append(result)
        return results

    async def plan_streaming(
        self,
        source_root: Path,
    ) -> AsyncIterator[WalkEvent]:
        """Yield walk-phase progress events for the bulk-import wizard.

        Plan 26 T3. This method exists ONLY to drive the SSE endpoint's
        progress UI — it does NOT classify, does NOT compute duplicate
        hints, does NOT return a :class:`BulkPlan`, and does NOT mutate
        the vault. The wizard calls :meth:`plan` separately AFTER the
        stream completes to obtain the actual planned items (D-decision
        (a) in ``tasks/plans/26-critical-fix-and-plan-25-aftermath.md``).

        Event sequence:

        - 1x :class:`WalkStarted` immediately, before the first ``os.scandir``.
        - 1x :class:`WalkProgress` every :data:`_WALK_PROGRESS_INTERVAL`
          candidate files counted. The counter increments BEFORE the
          system-file / extension filter so the user sees forward
          motion even when most of the tree is OS clutter.
        - 1x :class:`WalkComplete` on natural exit, carrying the final
          ``total_count`` of files that PASSED all filters AND were
          claimed by the dispatcher. ``plan_id`` is a fresh UUID4 for
          telemetry correlation only.
        - 1x :class:`WalkError` in place of :class:`WalkComplete` when
          the walk raises. The exception is re-raised AFTER the event
          is yielded so the endpoint sees a clean stream close + a
          structured failure for logging.

        Cancellation:

        :class:`asyncio.CancelledError` (from the ASGI request scope
        closing) is propagated WITHOUT emitting a :class:`WalkError` —
        the client is already gone; one final event would never reach
        them. The generator simply re-raises so the server-side stream
        wrapper can clean up.

        Filter parity with :meth:`plan`: this method MUST stay
        consistent with :meth:`plan` on which files count toward
        ``total_count``. Both paths share the helper triad
        :func:`_is_hidden`, :func:`_is_system_file`, and the
        :data:`_VALID_EXTENSIONS` whitelist, plus the
        :func:`brain_core.ingest.dispatcher.dispatch` claim check.
        """
        plan_id = str(uuid.uuid4())
        yield WalkStarted(path=str(source_root))

        files_seen = 0  # candidate-files counter (drives WalkProgress)
        total_count = 0  # files that passed every filter

        try:
            # Existence + readability are checked BEFORE walking because
            # ``Path.glob`` swallows FileNotFoundError / PermissionError
            # on the root directory itself and returns an empty iterator
            # — silently succeeding when the caller almost certainly
            # wants a structured error. The brain_api endpoint also runs
            # a pre-check but the model layer cannot assume that (this
            # method is called by tests and may be wired into other
            # consumers in the future).
            if not source_root.exists():
                exc_nf = FileNotFoundError(
                    f"source_root does not exist: {source_root}"
                )
                yield WalkError(
                    error_message=str(exc_nf),
                    error_code="path_not_found",
                )
                raise exc_nf
            if not source_root.is_dir():
                exc_nf = FileNotFoundError(
                    f"source_root is not a directory: {source_root}"
                )
                yield WalkError(
                    error_message=str(exc_nf),
                    error_code="path_not_found",
                )
                raise exc_nf
            try:
                # Touch the directory once so a chmod-0 dir surfaces as
                # PermissionError BEFORE glob silently returns empty.
                next(iter(source_root.iterdir()), None)
            except PermissionError as exc:
                yield WalkError(
                    error_message=str(exc),
                    error_code="permission_denied",
                )
                raise

            try:
                candidates = sorted(source_root.glob("**/*"))
            except FileNotFoundError as exc:
                yield WalkError(
                    error_message=str(exc),
                    error_code="path_not_found",
                )
                raise
            except PermissionError as exc:
                yield WalkError(
                    error_message=str(exc),
                    error_code="permission_denied",
                )
                raise

            for p in candidates:
                # Skip non-files and symlinks (consistent with plan()).
                if not p.is_file() or p.is_symlink():
                    continue

                # Increment the "seen" counter BEFORE the OS-clutter filter
                # so the user sees movement on noisy trees. WalkProgress
                # reports files-examined, not files-that-will-be-ingested.
                files_seen += 1
                if files_seen % _WALK_PROGRESS_INTERVAL == 0:
                    yield WalkProgress(files_seen=files_seen, current_path=str(p))

                # Hidden / system-file / extension filters — same triad as
                # plan(). Filtered files are silently dropped from the
                # total_count, matching the plan-view's "you never see OS
                # clutter" contract.
                if _is_hidden(p, root=source_root):
                    continue
                if _is_system_file(p.name):
                    continue
                try:
                    rel_parts = p.relative_to(source_root).parts
                except ValueError:
                    rel_parts = ()
                if any(_is_system_file(part) for part in rel_parts):
                    continue
                if p.suffix.lower() not in _VALID_EXTENSIONS:
                    continue

                # Dispatcher claim check — uses the pipeline's handler
                # list so config-supplied tunables match plan().
                try:
                    await dispatch(p, handlers=self._pipeline.handlers)
                except DispatchError:
                    # Claimed-but-unsupported — these land in plan.skipped
                    # for the wizard's review, but for progress-reporting
                    # purposes they DO NOT advance total_count.
                    continue

                total_count += 1

            yield WalkComplete(total_count=total_count, plan_id=plan_id)
        except asyncio.CancelledError:
            # Client disconnect mid-walk — let the request scope unwind
            # cleanly. Do NOT yield a WalkError (no one will receive it)
            # and do NOT swallow the cancel (the stream wrapper relies on
            # it for cleanup signaling).
            raise
        except (FileNotFoundError, PermissionError):
            # WalkError already yielded above; re-raise the original
            # exception so the endpoint can log it via structlog.
            raise
        except Exception as exc:
            yield WalkError(error_message=str(exc), error_code="internal_error")
            raise
