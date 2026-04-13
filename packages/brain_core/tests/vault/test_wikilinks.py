from __future__ import annotations

from pathlib import Path

from brain_core.vault.wikilinks import (
    BrokenLink,
    Resolved,
    extract_wikilinks,
    resolve_wikilinks,
)


def test_extract_basic() -> None:
    body = "See [[alpha]] and [[beta|the beta note]] and [[gamma]]."
    assert extract_wikilinks(body) == ["alpha", "beta", "gamma"]


def test_extract_ignores_code_fences() -> None:
    body = "```\n[[notalink]]\n```\nReal: [[yes]]"
    assert extract_wikilinks(body) == ["yes"]


def test_resolve_unique_target(ephemeral_vault: Path) -> None:
    (ephemeral_vault / "research" / "concepts" / "alpha.md").write_text("x", encoding="utf-8")
    out = resolve_wikilinks(
        ["alpha"],
        vault_root=ephemeral_vault,
        active_domain="research",
    )
    assert isinstance(out["alpha"], Resolved)
    assert out["alpha"].path.name == "alpha.md"


def test_resolve_broken(ephemeral_vault: Path) -> None:
    out = resolve_wikilinks(["ghost"], vault_root=ephemeral_vault, active_domain="research")
    assert isinstance(out["ghost"], BrokenLink)


def test_resolve_collision_prefers_active_domain(ephemeral_vault: Path) -> None:
    (ephemeral_vault / "research" / "concepts" / "dup.md").write_text("r", encoding="utf-8")
    (ephemeral_vault / "work" / "concepts" / "dup.md").write_text("w", encoding="utf-8")
    out = resolve_wikilinks(["dup"], vault_root=ephemeral_vault, active_domain="work")
    resolved = out["dup"]
    assert isinstance(resolved, Resolved)
    assert resolved.path.parts[-3] == "work"
