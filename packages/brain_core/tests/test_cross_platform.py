# packages/brain_core/tests/test_cross_platform.py
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from brain_core.vault.types import NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


def test_vault_accepts_paths_with_spaces_and_unicode(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "hello world — unicode ✓.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\ntitle: hi\n---\n\nbody\n")])
    vw.apply(ps, allowed_domains=("research",))
    assert target.exists()
    assert "body" in target.read_text(encoding="utf-8")


def test_lf_line_endings_on_disk(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "lf.md"
    content = "---\ntitle: lf\n---\n\nline1\nline2\n"
    ps = PatchSet(new_files=[NewFile(path=target, content=content)])
    vw.apply(ps, allowed_domains=("research",))
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == content.count("\n")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only reserved-name check")
def test_windows_reserved_name_rejected(ephemeral_vault: Path) -> None:
    # CON, PRN, AUX, NUL, COM1-9, LPT1-9 are reserved on Windows.
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "CON.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\n---\n")])
    with pytest.raises(OSError):
        vw.apply(ps, allowed_domains=("research",))
