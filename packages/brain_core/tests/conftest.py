"""Shared pytest fixtures for brain_core tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def ephemeral_vault(tmp_path: Path) -> Path:
    """Create a minimal, valid brain vault inside tmp_path and return its root.

    Layout:
        <tmp>/brain/
            .brain/
            research/  work/  personal/   # each with sources/entities/concepts/synthesis + index.md + log.md
            chats/{research,work,personal}/
            raw/{inbox,failed,archive}/
            BRAIN.md
    """
    root = tmp_path / "brain"
    root.mkdir()
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        d.mkdir()
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir()
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")
        (root / "chats" / domain).mkdir(parents=True)
    for sub in ("inbox", "failed", "archive"):
        (root / "raw" / sub).mkdir(parents=True)
    (root / "BRAIN.md").write_text("# BRAIN\n\nDefault schema doc.\n", encoding="utf-8")
    return root
