"""Shared fixtures for brain_api tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8", newline="\n")


@pytest.fixture
def seeded_vault(tmp_path: Path) -> Path:
    """A small research + work + personal vault used by all tests."""
    vault = tmp_path / "vault"
    _write_note(vault, "research/notes/karpathy.md", title="Karpathy", body="LLM wiki pattern.")
    _write_note(vault, "research/notes/rag.md", title="RAG", body="Retrieval-augmented generation.")
    (vault / "research" / "index.md").write_text(
        "# research\n- [[karpathy]]\n- [[rag]]\n", encoding="utf-8", newline="\n"
    )
    _write_note(vault, "work/notes/meeting.md", title="Meeting", body="Q4 planning.")
    (vault / "work" / "index.md").write_text(
        "# work\n- [[meeting]]\n", encoding="utf-8", newline="\n"
    )
    _write_note(vault, "personal/notes/secret.md", title="Secret", body="never read me")
    (vault / "BRAIN.md").write_text("# BRAIN\n\nYou are brain.\n", encoding="utf-8", newline="\n")
    return vault


@pytest.fixture
def app(seeded_vault: Path) -> FastAPI:
    """A FastAPI app bound to seeded_vault with allowed_domains=('research',)."""
    return create_app(vault_root=seeded_vault, allowed_domains=("research",))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Synchronous TestClient for quick REST assertions."""
    return TestClient(app)
