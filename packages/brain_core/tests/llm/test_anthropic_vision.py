"""Plan 24 Task 3 / D4 — :class:`AnthropicProvider.vision_extract` pin tests.

Pins the wire shape we send to the Anthropic SDK and the return-tuple
shape callers expect. Cases:

* (a) The call uses ``model``, ``max_tokens``, and a single ``user``
      message with an image block + text block.
* (b) The image block carries ``{"type": "image", "source": {"type":
      "base64", "media_type": <content_type>, "data": <base64>}}``.
* (c) Base64 encoding of ``image_bytes`` matches Python's
      ``standard_b64encode``.
* (d) The text block carries the prompt verbatim.
* (e) Default model = Sonnet 4.6 when caller omits ``model=``.
* (f) Explicit ``model="claude-opus-4-6"`` flows through.
* (g) Return tuple is (text, input_tokens, output_tokens) plumbed from
      the SDK response.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest
from brain_core.llm.providers.anthropic import AnthropicProvider


class _FakeVisionClient:
    """Records the kwargs passed to ``messages.create`` and returns a
    SimpleNamespace shaped like an Anthropic SDK ``Message``."""

    def __init__(
        self,
        *,
        return_text: str = "extracted text",
        input_tokens: int = 200,
        output_tokens: int = 12,
    ) -> None:
        self.messages = SimpleNamespace(create=self._create)
        self.last_kwargs: dict[str, Any] | None = None
        self._return_text = return_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def _create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._return_text)],
            usage=SimpleNamespace(
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
            ),
            stop_reason="end_turn",
            model=kwargs["model"],
        )


@pytest.mark.asyncio
async def test_vision_extract_calls_messages_create_with_image_content_block() -> None:
    """(a)+(b)+(d) Verify the messages.create kwargs structure."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    await provider.vision_extract(
        b"\x89PNG\r\n\x1a\nfake-png-bytes",
        "Extract any text visible in this image.",
        content_type="image/png",
    )

    assert client.last_kwargs is not None
    messages = client.last_kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    content = messages[0]["content"]
    # Block 0: image
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/png"
    # Block 1: text (prompt)
    assert content[1]["type"] == "text"
    assert content[1]["text"] == "Extract any text visible in this image."


@pytest.mark.asyncio
async def test_vision_extract_base64_encodes_image_bytes() -> None:
    """(c) ``source.data`` is ``base64.standard_b64encode(image_bytes).decode()``."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    raw = b"some-image-bytes-here"
    expected_b64 = base64.standard_b64encode(raw).decode("utf-8")

    await provider.vision_extract(raw, "prompt")

    assert client.last_kwargs is not None
    assert client.last_kwargs["messages"][0]["content"][0]["source"]["data"] == expected_b64


@pytest.mark.asyncio
async def test_vision_extract_default_model_is_sonnet_4_6() -> None:
    """(e) Caller omits ``model``; default ``claude-sonnet-4-6`` used."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    await provider.vision_extract(b"x", "p")

    assert client.last_kwargs is not None
    assert client.last_kwargs["model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_vision_extract_explicit_model_override() -> None:
    """(f) Caller passes ``model="claude-opus-4-6"``; that string flows through."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    await provider.vision_extract(b"x", "p", model="claude-opus-4-6")

    assert client.last_kwargs is not None
    assert client.last_kwargs["model"] == "claude-opus-4-6"


@pytest.mark.asyncio
async def test_vision_extract_returns_text_and_token_tuple() -> None:
    """(g) Return tuple is (text, input_tokens, output_tokens) from the SDK response."""
    client = _FakeVisionClient(
        return_text="hello from vision",
        input_tokens=333,
        output_tokens=44,
    )
    provider = AnthropicProvider(api_key="sk-test", client=client)

    text, in_tokens, out_tokens = await provider.vision_extract(b"x", "p")

    assert text == "hello from vision"
    assert in_tokens == 333
    assert out_tokens == 44


@pytest.mark.asyncio
async def test_vision_extract_max_tokens_capped_at_1024() -> None:
    """OCR is text-only; max_tokens=1024 ceiling pins against runaway responses."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    await provider.vision_extract(b"x", "p")

    assert client.last_kwargs is not None
    assert client.last_kwargs["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_vision_extract_passes_explicit_content_type() -> None:
    """``content_type="image/jpeg"`` flows into ``source.media_type``."""
    client = _FakeVisionClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    await provider.vision_extract(b"x", "p", content_type="image/jpeg")

    assert client.last_kwargs is not None
    media_type = client.last_kwargs["messages"][0]["content"][0]["source"]["media_type"]
    assert media_type == "image/jpeg"


@pytest.mark.asyncio
async def test_vision_extract_concatenates_multiple_text_blocks() -> None:
    """SDK may return multiple text blocks; we concatenate them in order."""

    class _MultiBlockClient(_FakeVisionClient):
        async def _create(self, **kwargs: Any) -> Any:
            self.last_kwargs = kwargs
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="part one. "),
                    SimpleNamespace(type="text", text="part two."),
                ],
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                stop_reason="end_turn",
                model=kwargs["model"],
            )

    client = _MultiBlockClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)

    text, _, _ = await provider.vision_extract(b"x", "p")
    assert text == "part one. part two."
