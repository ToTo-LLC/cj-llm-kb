from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from brain_core.llm.providers.anthropic import AnthropicProvider
from brain_core.llm.types import LLMMessage, LLMRequest


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = SimpleNamespace(create=self._create)
        self.last_kwargs: dict[str, Any] | None = None

    async def _create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            usage=SimpleNamespace(input_tokens=12, output_tokens=3),
            stop_reason="end_turn",
            model=kwargs["model"],
        )


@pytest.mark.asyncio
async def test_anthropic_complete_translates_request_and_response() -> None:
    client = _FakeAnthropicClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
        system="you are brain",
    )
    resp = await provider.complete(req)
    assert resp.content == "hello"
    assert resp.usage.input_tokens == 12
    assert resp.usage.output_tokens == 3
    assert client.last_kwargs is not None
    assert client.last_kwargs["system"] == "you are brain"
    assert client.last_kwargs["messages"][0]["role"] == "user"
