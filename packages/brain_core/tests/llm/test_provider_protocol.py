from __future__ import annotations

from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.provider import LLMProvider


def test_fake_satisfies_protocol() -> None:
    p: LLMProvider = FakeLLMProvider()
    assert p is not None
