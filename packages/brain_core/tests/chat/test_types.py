"""Tests for brain_core.chat.types — the typed surface every downstream module imports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.chat.types import (
    ChatEvent,
    ChatEventKind,
    ChatMode,
    ChatSessionConfig,
    ChatTurn,
    TurnRole,
)
from pydantic import ValidationError


class TestChatMode:
    def test_members_are_ask_brainstorm_draft(self) -> None:
        assert set(ChatMode) == {ChatMode.ASK, ChatMode.BRAINSTORM, ChatMode.DRAFT}

    def test_values_are_lowercase_strings(self) -> None:
        assert ChatMode.ASK.value == "ask"
        assert ChatMode.BRAINSTORM.value == "brainstorm"
        assert ChatMode.DRAFT.value == "draft"

    def test_str_enum_equality(self) -> None:
        # StrEnum members compare equal to their string value at runtime.
        value: str = "ask"
        assert value == ChatMode.ASK


class TestChatTurn:
    def test_user_turn_round_trip(self) -> None:
        turn = ChatTurn(
            role=TurnRole.USER,
            content="hello",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[],
            cost_usd=0.0,
        )
        assert turn.role == TurnRole.USER
        assert turn.content == "hello"
        assert turn.cost_usd == 0.0

    def test_assistant_turn_accepts_tool_calls(self) -> None:
        turn = ChatTurn(
            role=TurnRole.ASSISTANT,
            content="looking that up",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[
                {"name": "search_vault", "args": {"query": "karpathy"}, "result_preview": "1 hit"},
            ],
            cost_usd=0.0012,
        )
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0]["name"] == "search_vault"

    def test_system_turn_for_mode_switch(self) -> None:
        turn = ChatTurn(
            role=TurnRole.SYSTEM,
            content="mode changed: ask -> brainstorm",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[],
            cost_usd=0.0,
        )
        assert turn.role == TurnRole.SYSTEM

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatTurn(
                role=TurnRole.ASSISTANT,
                content="x",
                created_at=datetime(2026, 4, 14, tzinfo=UTC),
                tool_calls=[],
                cost_usd=-0.01,
            )


class TestChatEvent:
    def test_delta_event(self) -> None:
        ev = ChatEvent(kind=ChatEventKind.DELTA, data={"text": "hel"})
        assert ev.kind == ChatEventKind.DELTA
        assert ev.data["text"] == "hel"

    def test_tool_call_event(self) -> None:
        ev = ChatEvent(
            kind=ChatEventKind.TOOL_CALL,
            data={"name": "search_vault", "args": {"query": "x"}},
        )
        assert ev.kind == ChatEventKind.TOOL_CALL

    def test_all_kinds_present(self) -> None:
        assert set(ChatEventKind) == {
            ChatEventKind.DELTA,
            ChatEventKind.TOOL_CALL,
            ChatEventKind.TOOL_RESULT,
            ChatEventKind.TURN_END,
            ChatEventKind.COST_UPDATE,
            ChatEventKind.PATCH_PROPOSED,
            # Plan 07 Task 2: Draft-mode structured-edit signal.
            ChatEventKind.DOC_EDIT,
            ChatEventKind.ERROR,
        }


class TestChatSessionConfig:
    def test_defaults(self) -> None:
        cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
        assert cfg.mode == ChatMode.ASK
        assert cfg.domains == ("research",)
        assert cfg.open_doc_path is None
        assert cfg.context_cap_tokens == 150_000
        assert cfg.model == "claude-sonnet-4-6"

    def test_draft_mode_with_open_doc(self) -> None:
        cfg = ChatSessionConfig(
            mode=ChatMode.DRAFT,
            domains=("work",),
            open_doc_path=Path("work/notes/plan.md"),
        )
        assert cfg.open_doc_path == Path("work/notes/plan.md")

    def test_empty_domains_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatSessionConfig(mode=ChatMode.ASK, domains=())

    def test_personal_in_domains_allowed_explicitly(self) -> None:
        cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("personal",))
        assert "personal" in cfg.domains
