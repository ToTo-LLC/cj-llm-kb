"""Tests for brain_core.chat.autotitle.AutoTitler."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brain_core.chat.autotitle import AutoTitleError, AutoTitler
from brain_core.chat.types import ChatTurn, TurnRole
from brain_core.llm.fake import FakeLLMProvider


def _turn(role: TurnRole, content: str) -> ChatTurn:
    return ChatTurn(role=role, content=content, created_at=datetime(2026, 4, 14, tzinfo=UTC))


@pytest.fixture
def turns() -> list[ChatTurn]:
    return [
        _turn(TurnRole.USER, "tell me about the karpathy llm wiki pattern"),
        _turn(
            TurnRole.ASSISTANT,
            "The LLM wiki pattern compiles raw notes into a curated wiki.",
        ),
    ]


async def test_run_returns_validated_title(turns: list[ChatTurn]) -> None:
    fake = FakeLLMProvider()
    fake.queue('{"title": "karpathy llm wiki", "slug": "karpathy-llm-wiki"}')
    autotitler = AutoTitler(llm=fake)
    result = await autotitler.run(turns)
    assert result.title == "karpathy llm wiki"
    assert result.slug == "karpathy-llm-wiki"


async def test_invalid_json_raises_autotitle_error(turns: list[ChatTurn]) -> None:
    fake = FakeLLMProvider()
    fake.queue("not json at all")
    autotitler = AutoTitler(llm=fake)
    with pytest.raises(AutoTitleError, match="non-JSON"):
        await autotitler.run(turns)


async def test_slug_mismatch_raises(turns: list[ChatTurn]) -> None:
    fake = FakeLLMProvider()
    fake.queue('{"title": "foo bar", "slug": "completely-different"}')
    autotitler = AutoTitler(llm=fake)
    with pytest.raises(AutoTitleError, match="slug"):
        await autotitler.run(turns)
