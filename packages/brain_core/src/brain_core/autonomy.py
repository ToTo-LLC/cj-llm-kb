"""Autonomy gate — decide whether a :class:`PatchSet` may auto-apply for
a given target domain.

The autonomy gate is the ONLY narrowly-scoped exception to CLAUDE.md
principle #3 ("LLM writes are always staged, never direct"). It looks at
the patchset's ``category`` AND the populated PatchSet member fields,
cross-references them against the per-domain
:class:`brain_core.config.schema.AutonomyCategoryFlags` for the patch's
target domain, and returns True iff every required flag is True. When
that happens, :func:`brain_core.tools.apply_patch.handle` auto-applies
the patch instead of staging it.

**Plan 16 Task 39 — HYBRID per-domain x per-category gate.**

Algorithm (locked in T37 §5, sign-off in T39 dispatch D-1):

1. ``PatchCategory.OTHER`` always returns False (preserved invariant).
2. ``flags = config.autonomous.get(domain)`` — a missing entry means
   "all-False for this domain", and the gate returns False whenever
   any non-trivial work is requested.
3. Build the required-True set:

   * For every non-empty PatchSet member field
     (``new_files`` / ``edits`` / ``index_entries``), require the
     same-named flag on :class:`AutonomyCategoryFlags`.
   * For ``category in {CONCEPTS, DRAFT}``, additionally require the
     same-named category flag (``flags.concepts`` / ``flags.draft``).
   * For ``category in {INGEST, ENTITIES, INDEX_REWRITES}``, NO extra
     category-level requirement: member-field flags govern alone.

4. Return True iff every required flag is True. ANY-False ⇒ stage the
   whole patch (intersection across all required flags — no partial
   apply).

The hybrid surface is intentional. Chat-mode autonomy ("draft a note
for me") is naturally category-shaped, while ingest / propose-note
autonomy is naturally member-field-shaped (the user reasons about
"do I trust auto-creating new files?" not "do I trust the INGEST
bucket?"). See T37 §1 for the full rationale.

Safety invariants pinned by ``tests/test_autonomy.py``:

* :attr:`PatchCategory.OTHER` NEVER auto-applies. The default
  category on every new ``PatchSet`` is OTHER, so a caller that
  forgets to stamp a category cannot accidentally bypass the
  approval queue.
* Default :class:`AutonomyCategoryFlags` has every flag ``False``,
  so the gate is off until the user explicitly opts in.
* No cross-category leakage and no cross-domain leakage: enabling
  flags in one domain does not affect another.
"""

from __future__ import annotations

from brain_core.config.schema import Config
from brain_core.vault.types import PatchCategory, PatchSet

__all__ = ["should_auto_apply"]

# Categories whose patches require the same-named category flag in
# addition to the member-field flags. Per T37 D-1 HYBRID:
# INGEST / ENTITIES / INDEX_REWRITES are member-field-only;
# CONCEPTS / DRAFT also require their category flag.
_CATEGORY_REQUIRES_OWN_FLAG: dict[PatchCategory, str] = {
    PatchCategory.CONCEPTS: "concepts",
    PatchCategory.DRAFT: "draft",
}


def should_auto_apply(
    patchset: PatchSet,
    config: Config,
    *,
    domain: str,
) -> bool:
    """Per-domain x per-category gate. Returns True iff this patchset's
    content is fully covered by enabled flags for ``domain``.

    Parameters are keyword-only after ``config`` to force every caller
    to migrate explicitly to the per-domain shape (Plan 16 Task 39).
    Missing-domain entries (or an empty string for ``domain``) match
    "all-False" semantics and stage every non-trivial patch.
    """
    # 1. OTHER never auto-applies — preserved invariant.
    if patchset.category == PatchCategory.OTHER:
        return False

    # 2. No autonomy entry for this domain ⇒ all-False ⇒ stage.
    flags = config.autonomous.get(domain)
    if flags is None:
        return False

    # 3a. Member-field flags: every populated member field requires its
    # same-named flag. ANY-False ⇒ stage (intersection semantics).
    if patchset.new_files and not flags.new_files:
        return False
    if patchset.edits and not flags.edits:
        return False
    if patchset.index_entries and not flags.index_entries:
        return False

    # 3b. Category flag (only for CONCEPTS / DRAFT under HYBRID). 4. Every
    # required flag is True. The compound return below mirrors the
    # algorithm's "intersection / require-True" framing — collapsing it
    # via the SIM103 inline-negation transform makes the docstring
    # mapping harder to read, so we accept the explicit `is not None`.
    category_flag = _CATEGORY_REQUIRES_OWN_FLAG.get(patchset.category)
    if category_flag is None:
        return True
    return bool(getattr(flags, category_flag))
