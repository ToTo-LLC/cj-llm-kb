from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.vault.paths import ScopeError, scope_guard


def test_allows_path_inside_allowed_domain(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "research" / "sources" / "note.md"
    result = scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))
    assert result == p.resolve()


def test_rejects_path_in_disallowed_domain(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "personal" / "sources" / "note.md"
    with pytest.raises(ScopeError, match="not in allowed"):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_rejects_dotdot_escape(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "research" / ".." / ".." / "etc" / "passwd"
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_rejects_absolute_outside_vault(ephemeral_vault: Path, tmp_path: Path) -> None:
    p = tmp_path / "outside.md"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research",))


def test_allows_cross_domain_when_all_listed(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "work" / "sources" / "n.md"
    scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research", "work", "personal"))


def test_personal_never_matches_wildcard_research_only(ephemeral_vault: Path) -> None:
    p = ephemeral_vault / "personal" / "concepts" / "private.md"
    with pytest.raises(ScopeError):
        scope_guard(p, vault_root=ephemeral_vault, allowed_domains=("research", "work"))
