"""BulkImporter — folder-level dry-run / apply wrapper around IngestPipeline.

Workflow:
  1. Call `plan(folder, ...)` to walk the folder, run the classifier (or skip if
     domain_override is set), and build a BulkPlan without touching the vault.
  2. Inspect the plan (print it, present it to the user, etc.).
  3. Call `apply(plan, ...)` to run the full IngestPipeline per item and return
     a list of IngestResult in the same order as plan.items.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from brain_core.ingest.classifier import classify
from brain_core.ingest.dispatcher import DispatchError, dispatch
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestResult


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

            # Check that a handler claims this file
            try:
                await dispatch(p)
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

        Returns a list of IngestResult in the same order as plan.items. Does
        NOT short-circuit on FAILED items — each item is independent.
        """
        results: list[IngestResult] = []
        for item in plan.items:
            effective_override = domain_override or item.classified_domain
            result = await self._pipeline.ingest(
                item.spec,
                allowed_domains=allowed_domains,
                domain_override=effective_override,
            )
            results.append(result)
        return results
