"""Plan 10 Task 2 — ``scope_guard`` works with non-default domain sets.

The v0.1 ``scope_guard`` already accepted a per-call ``allowed_domains``
iterable, but no test exercised it with a vault whose on-disk domains
differed from the v0.1 ``{research, work, personal}`` triple. These
tests pin the dynamic case so the privacy rail can't silently regress
when the user adds a domain via Settings → Domains.

The Plan 10 Task 2 spec asks for two assertions:

1. A vault with ``{research, hobby, personal}`` accepts
   ``hobby/notes/foo.md`` and rejects ``work/notes/foo.md``.
2. ``personal`` stays scope-guarded as before — adding a domain to the
   live set does NOT loosen the privacy rail; the caller still has to
   pass ``"personal"`` in ``allowed_domains`` for a personal path to
   resolve.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError, scope_guard


def _make_vault(root: Path, domains: tuple[str, ...]) -> Path:
    """Create a minimal vault layout for the given domain slugs."""
    root.mkdir(parents=True, exist_ok=True)
    (root / ".brain").mkdir(exist_ok=True)
    for domain in domains:
        (root / domain / "notes").mkdir(parents=True, exist_ok=True)
        (root / domain / "notes" / "foo.md").write_text("seed\n", encoding="utf-8")
    return root


def test_scope_guard_accepts_user_added_domain(tmp_path: Path) -> None:
    """A user-added domain (``hobby``) is accepted by ``scope_guard``."""
    vault = _make_vault(tmp_path / "brain", ("research", "hobby", "personal"))
    note = vault / "hobby" / "notes" / "foo.md"
    result = scope_guard(
        note,
        vault_root=vault,
        allowed_domains=("research", "hobby", "personal"),
    )
    assert result == note.resolve()


def test_scope_guard_rejects_path_for_domain_not_in_live_set(tmp_path: Path) -> None:
    """A path whose first component isn't in ``allowed_domains`` is rejected.

    Even though the ``work`` directory does not exist on disk for this
    vault, ``scope_guard`` should refuse the path purely on the live
    domain set — it never trusts the filesystem to enforce scope.
    """
    vault = _make_vault(tmp_path / "brain", ("research", "hobby", "personal"))
    work_note = vault / "work" / "notes" / "foo.md"
    work_note.parent.mkdir(parents=True, exist_ok=True)
    work_note.write_text("smuggled\n", encoding="utf-8")
    with pytest.raises(ScopeError, match="not in allowed"):
        scope_guard(
            work_note,
            vault_root=vault,
            allowed_domains=("research", "hobby", "personal"),
        )


def test_personal_remains_scope_guarded_when_extra_domains_present(
    tmp_path: Path,
) -> None:
    """Adding ``hobby`` to the domain set does not unlock ``personal``.

    The privacy rail in v0.1 was: callers default to
    ``allowed_domains=("research", "work")`` so ``personal/...`` is
    rejected. Plan 10 must preserve this — when the live domain set is
    ``{research, hobby, personal}`` but the per-call scope is
    ``{research, hobby}``, ``personal/...`` must still raise.
    """
    vault = _make_vault(tmp_path / "brain", ("research", "hobby", "personal"))
    private = vault / "personal" / "notes" / "foo.md"
    with pytest.raises(ScopeError, match="not in allowed"):
        scope_guard(
            private,
            vault_root=vault,
            allowed_domains=("research", "hobby"),
        )


def test_default_domain_set_still_works_after_constant_drop(tmp_path: Path) -> None:
    """Plan 02's v0.1 vault still validates after Task 2 dropped the
    ``ALLOWED_DOMAINS`` module constant.

    This is a belt-and-braces check that ``scope_guard`` does not
    secretly depend on the constant for the v0.1 default triple — the
    plan note for this task ("Plan 02's test_paths.py uses string
    literals for domain names; verify they still pass with the dropped
    constant") motivates this regression pin.
    """
    vault = _make_vault(tmp_path / "brain", ("research", "work", "personal"))
    note = vault / "work" / "notes" / "foo.md"
    result = scope_guard(
        note,
        vault_root=vault,
        allowed_domains=("research", "work"),
    )
    assert result == note.resolve()
