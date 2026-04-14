"""Tests for brain_core.chat.context.ContextCompiler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.chat.context import ContextCompiler
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "index.md").write_text(
        "# research index\n- [[karpathy]]\n", encoding="utf-8"
    )
    (tmp_path / "BRAIN.md").write_text("# BRAIN\n\nYou are brain.\n", encoding="utf-8")
    return tmp_path


def _turn(role: TurnRole, content: str) -> ChatTurn:
    return ChatTurn(role=role, content=content, created_at=datetime(2026, 4, 14, tzinfo=UTC))


def test_compiles_brain_md_and_index(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="You are ASK mode.")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="hello")
    assert "You are brain." in ctx.system
    assert "You are ASK mode." in ctx.system
    assert "# research index" in ctx.system


def test_missing_brain_md_is_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()
    compiler = ContextCompiler(vault_root=tmp_path, mode_prompt="ASK MODE PROMPT")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="hi")
    assert "ASK MODE PROMPT" in ctx.system
    # No BRAIN.md content should appear.
    assert "brain" not in ctx.system.lower() or "brain" in "ASK MODE PROMPT".lower()


def test_read_notes_included_as_system_blocks(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(
        cfg,
        turns=[],
        read_notes={Path("research/notes/karpathy.md"): "# Karpathy\n\nLLM wiki pattern."},
        user_message="q",
    )
    assert "research/notes/karpathy.md" in ctx.system
    assert "LLM wiki pattern" in ctx.system


def test_turns_and_user_message_in_messages(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    turns = [
        _turn(TurnRole.USER, "first question"),
        _turn(TurnRole.ASSISTANT, "first answer"),
    ]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="second question")
    assert ctx.messages[0] == {"role": "user", "content": "first question"}
    assert ctx.messages[1] == {"role": "assistant", "content": "first answer"}
    assert ctx.messages[-1] == {"role": "user", "content": "second question"}


def test_system_turn_becomes_assistant_note(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    turns = [_turn(TurnRole.SYSTEM, "mode changed: ask -> brainstorm")]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="q")
    assert any("mode changed" in m["content"] for m in ctx.messages)
    # The SYSTEM turn surfaces as role="assistant" with a [system] prefix.
    system_turn_msg = next(m for m in ctx.messages if "mode changed" in m["content"])
    assert system_turn_msg["role"] == "assistant"
    assert system_turn_msg["content"].startswith("[system]")


def test_context_cap_trims_oldest_turns(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",), context_cap_tokens=50)
    # ~1600 chars → ~400 tokens under len//4
    big = "word " * 320
    turns = [
        _turn(TurnRole.USER, "ancient turn 1"),
        _turn(TurnRole.ASSISTANT, big),
        _turn(TurnRole.USER, "recent turn"),
    ]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="now")
    contents = [m["content"] for m in ctx.messages]
    # New user message survives.
    assert "now" in contents
    # Oldest turn trimmed.
    assert "ancient turn 1" not in contents


def test_cap_never_trims_user_message_or_system(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK MODE PROMPT")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",), context_cap_tokens=5)
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="MUST SURVIVE")
    assert any("MUST SURVIVE" in m["content"] for m in ctx.messages)
    assert "ASK MODE PROMPT" in ctx.system
