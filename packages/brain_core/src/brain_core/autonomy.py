"""Autonomy gate — decide whether a :class:`PatchSet` may auto-apply.

The autonomy gate is the ONLY narrowly-scoped exception to CLAUDE.md
principle #3 ("LLM writes are always staged, never direct"). It looks at
the PatchSet's ``category`` and the matching per-category flag in
``Config.autonomous``; if the flag is ``True``, the patch is auto-applied
by :func:`brain_core.tools.apply_patch.handle` instead of being staged.

Safety invariants pinned by ``tests/test_autonomy.py``:

* :attr:`PatchCategory.OTHER` NEVER auto-applies. The default category on
  every new ``PatchSet`` is OTHER, so a caller that forgets to stamp a
  category cannot accidentally bypass the approval queue.
* Default :class:`AutonomousConfig` has every flag ``False``, so the gate
  is off until the user explicitly opts in.
* No cross-category leakage: enabling ``autonomous.ingest`` does not cause
  ``PatchCategory.ENTITIES`` patches to auto-apply.
"""

from __future__ import annotations

from brain_core.config.schema import Config
from brain_core.vault.types import PatchCategory, PatchSet

__all__ = ["should_auto_apply"]

# Map each auto-appliable PatchCategory to its Config.autonomous attribute
# name. OTHER is intentionally absent — it always returns False and can
# never be opted into auto-apply.
_CATEGORY_TO_FLAG: dict[PatchCategory, str] = {
    PatchCategory.INGEST: "ingest",
    PatchCategory.ENTITIES: "entities",
    PatchCategory.CONCEPTS: "concepts",
    PatchCategory.INDEX_REWRITES: "index_rewrites",
    PatchCategory.DRAFT: "draft",
}


def should_auto_apply(patchset: PatchSet, config: Config) -> bool:
    """Return True iff this patchset's category is opted into auto-apply."""
    flag_name = _CATEGORY_TO_FLAG.get(patchset.category)
    if flag_name is None:
        # OTHER (and any future unmapped category) always stages.
        return False
    return bool(getattr(config.autonomous, flag_name))
