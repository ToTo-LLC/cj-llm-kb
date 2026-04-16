"""brain://BRAIN.md resource — the vault-root BRAIN.md (system prompt / working rules)."""

from __future__ import annotations

from pathlib import Path

URI = "brain://BRAIN.md"
NAME = "BRAIN.md"
DESCRIPTION = "Vault-root BRAIN.md — the user's system prompt and working rules."
MIME_TYPE = "text/markdown"


def read(vault_root: Path) -> str:
    """Return BRAIN.md body, or empty string if it doesn't exist yet.

    Non-existent BRAIN.md is a valid pre-setup state, not an error. Callers
    can inspect the return value to decide whether to nudge the user to run
    `brain setup`.
    """
    brain_md = vault_root / "BRAIN.md"
    if not brain_md.exists():
        return ""
    return brain_md.read_text(encoding="utf-8")
