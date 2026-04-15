"""Tests for brain_cli.session_factory."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from brain_cli.session_factory import _new_draft_thread_id, build_session
from brain_core.chat.types import ChatMode
from brain_core.llm.fake import FakeLLMProvider


def _seed_vault(root: Path) -> None:
    (root / "research").mkdir(parents=True)
    (root / "research" / "index.md").write_text("# research\n", encoding="utf-8")


def test_build_session_with_fake_llm(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    session = build_session(
        mode=ChatMode.ASK,
        domains=("research",),
        open_doc=None,
        model="claude-sonnet-4-6",
        vault_root=vault,
        llm=FakeLLMProvider(),
    )
    assert session.config.mode == ChatMode.ASK
    assert session.config.domains == ("research",)
    assert "draft" in session.thread_id
    assert session.vault_root == vault
    assert session.vault_writer is not None
    assert session.autotitler is not None


def test_build_session_missing_api_key_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    vault = tmp_path / "vault"
    _seed_vault(vault)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_session(
            mode=ChatMode.ASK,
            domains=("research",),
            open_doc=None,
            model="claude-sonnet-4-6",
            vault_root=vault,
        )


def test_new_draft_thread_id_format() -> None:
    id_1 = _new_draft_thread_id()
    id_2 = _new_draft_thread_id()
    assert re.match(r"^\d{4}-\d{2}-\d{2}-draft-[0-9a-f]{6}$", id_1)
    assert re.match(r"^\d{4}-\d{2}-\d{2}-draft-[0-9a-f]{6}$", id_2)
    assert id_1 != id_2
