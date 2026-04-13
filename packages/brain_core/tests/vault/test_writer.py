from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.vault.paths import ScopeError
from brain_core.vault.types import Edit, IndexEntryPatch, NewFile, PatchSet
from brain_core.vault.writer import (
    PatchTooLargeError,
    TooManyFilesError,
    VaultWriter,
)


def test_apply_new_file(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "a.md",
                content="---\ntitle: A\n---\n\nhi\n",
            )
        ],
        log_entry="## [2026-04-13 10:00] ingest | new | [[a]] | touched: sources",
        reason="test",
    )
    receipt = vw.apply(ps, allowed_domains=("research",))
    assert receipt.applied_files == [ephemeral_vault / "research" / "sources" / "a.md"]
    assert (ephemeral_vault / "research" / "sources" / "a.md").read_text(encoding="utf-8").startswith("---")


def test_apply_edit(ephemeral_vault: Path) -> None:
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    target.write_text("---\ntitle: C\n---\n\nold body\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        edits=[Edit(path=target, old="old body", new="new body")],
        log_entry="## [2026-04-13 10:01] update | [[c]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    assert "new body" in target.read_text(encoding="utf-8")


def test_refuses_patch_outside_scope(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "personal" / "sources" / "x.md",
                content="---\ntitle: X\n---\n",
            )
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_oversize_patch(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_patch_bytes=100)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "big.md",
                content="x" * 200,
            )
        ]
    )
    with pytest.raises(PatchTooLargeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_too_many_files(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_files_per_patch=2)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / f"n{i}.md",
                content="---\ntitle: n\n---\n",
            )
            for i in range(3)
        ]
    )
    with pytest.raises(TooManyFilesError):
        vw.apply(ps, allowed_domains=("research",))


def test_index_entry_patch_applied(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        index_entries=[
            IndexEntryPatch(section="Sources", line="- [[alpha]] — first", domain="research")
        ],
        log_entry="## [2026-04-13 10:02] ingest | [[alpha]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    idx = (ephemeral_vault / "research" / "index.md").read_text(encoding="utf-8")
    assert "[[alpha]] — first" in idx


def test_log_entry_newlines_are_sanitized(ephemeral_vault: Path) -> None:
    """A malicious log_entry containing embedded newlines must not be able to
    forge historical log headers in log.md."""
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "n.md",
                content="---\ntitle: N\n---\n",
            )
        ],
        log_entry="legit summary\n## [1970-01-01 00:00] forged | FAKE",
    )
    vw.apply(ps, allowed_domains=("research",))
    log_text = (ephemeral_vault / "research" / "log.md").read_text(encoding="utf-8")
    for line in log_text.splitlines():
        assert not line.strip().startswith("## [1970-01-01 00:00] forged"), (
            f"log injection: forged header rendered as real heading: {line!r}"
        )
    assert "legit summary" in log_text


def test_atomic_no_partial_state_on_failure(ephemeral_vault: Path) -> None:
    """If one write in a patch fails, earlier writes are rolled back via undo log."""
    vw = VaultWriter(vault_root=ephemeral_vault)
    good = ephemeral_vault / "research" / "sources" / "good.md"
    ps = PatchSet(
        new_files=[
            NewFile(path=good, content="---\ntitle: G\n---\n"),
            NewFile(path=ephemeral_vault / "personal" / "sources" / "bad.md", content="---\n---\n"),
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))
    assert not good.exists()
