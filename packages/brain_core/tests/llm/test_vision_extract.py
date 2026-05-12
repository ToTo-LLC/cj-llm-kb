"""Plan 24 Task 3 / D4 — :meth:`LLMProvider.vision_extract` pin tests.

Cases pinned per the plan-doc:

* (1) FakeLLMProvider returns the queued response (text + tokens).
* (2) FakeLLMProvider captures the call args (image bytes len, prompt,
      content_type, model).
* (3) Default ``content_type="image/png"`` flows through when caller
      omits the kwarg.
* (4) Explicit ``content_type="image/jpeg"`` is passed through.
* (5) Empty queue raises ``RuntimeError`` (mirrors the ``complete``
      queue contract — Plan 02 shape).

Plus protocol-shape pins:

* (6) :class:`FakeLLMProvider` still satisfies :class:`LLMProvider`
      after adding ``vision_extract`` to the Protocol (no regression).
* (7) ``vision_extract`` is reachable via the Protocol type (caller
      code that types against the Protocol can invoke the method).
"""

from __future__ import annotations

import pytest
from brain_core.llm.fake import FakeLLMProvider, FakeVisionResponse
from brain_core.llm.provider import LLMProvider


@pytest.mark.asyncio
async def test_vision_extract_returns_queued_response() -> None:
    """(1) Queue a response; assert text + token counts come back."""
    fake = FakeLLMProvider()
    fake.queue_vision("Extracted: hello world", input_tokens=42, output_tokens=7)

    text, in_tokens, out_tokens = await fake.vision_extract(
        b"\x89PNG\r\n\x1a\nfake-bytes", "Extract any text."
    )

    assert text == "Extracted: hello world"
    assert in_tokens == 42
    assert out_tokens == 7


@pytest.mark.asyncio
async def test_vision_extract_captures_call_args() -> None:
    """(2) Fake records (image_bytes_len, prompt, content_type, model)."""
    fake = FakeLLMProvider()
    fake.queue_vision("ok")

    await fake.vision_extract(
        b"abcdef",
        "find text",
        content_type="image/jpeg",
        model="claude-sonnet-4-6",
    )

    assert len(fake.vision_calls) == 1
    call = fake.vision_calls[0]
    assert call.image_bytes_len == 6
    assert call.prompt == "find text"
    assert call.content_type == "image/jpeg"
    assert call.model == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_vision_extract_uses_default_content_type() -> None:
    """(3) Caller omits content_type; default 'image/png' applied."""
    fake = FakeLLMProvider()
    fake.queue_vision("ok")

    await fake.vision_extract(b"xyz", "extract")

    assert fake.vision_calls[0].content_type == "image/png"


@pytest.mark.asyncio
async def test_vision_extract_uses_explicit_content_type() -> None:
    """(4) Caller passes content_type='image/jpeg'; that value flows through."""
    fake = FakeLLMProvider()
    fake.queue_vision("ok")

    await fake.vision_extract(b"xyz", "extract", content_type="image/jpeg")

    assert fake.vision_calls[0].content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_vision_extract_raises_when_queue_empty() -> None:
    """(5) Empty queue is programmer error: raises ``RuntimeError``.

    Mirrors Plan 02 ``complete`` queue contract — empty queue must
    fail loudly so tests that forget to prime don't silently pass
    with empty text.
    """
    fake = FakeLLMProvider()

    with pytest.raises(RuntimeError, match="vision queue is empty"):
        await fake.vision_extract(b"xyz", "extract")


def test_fake_still_satisfies_protocol() -> None:
    """(6) After adding vision_extract to the Protocol, FakeLLMProvider
    must still type-check as an :class:`LLMProvider`. ``isinstance``
    against a ``@runtime_checkable`` Protocol verifies the method
    set at runtime.
    """
    fake = FakeLLMProvider()
    assert isinstance(fake, LLMProvider)


@pytest.mark.asyncio
async def test_vision_extract_reachable_via_protocol() -> None:
    """(7) A caller typed against :class:`LLMProvider` can invoke
    ``vision_extract`` — confirms the Protocol carries the method.
    """
    provider: LLMProvider = FakeLLMProvider()
    # Cast through the protocol to confirm the attribute exists.
    assert hasattr(provider, "vision_extract")
    # Prime + invoke via the protocol-typed binding.
    provider_cast = provider  # type: ignore[assignment]
    # Cast back to FakeLLMProvider just to call the helper queue
    # method (queue_vision isn't on the Protocol — only on the fake).
    assert isinstance(provider_cast, FakeLLMProvider)
    provider_cast.queue_vision("yes")
    text, _, _ = await provider.vision_extract(b"x", "p")
    assert text == "yes"


@pytest.mark.asyncio
async def test_queue_vision_response_object_form() -> None:
    """The verbose-style ``queue_vision_response(FakeVisionResponse)`` works
    alongside the convenience ``queue_vision(text, ...)`` shape.
    """
    fake = FakeLLMProvider()
    fake.queue_vision_response(FakeVisionResponse(text="obj", input_tokens=1, output_tokens=2))
    text, in_tokens, out_tokens = await fake.vision_extract(b"x", "p")
    assert (text, in_tokens, out_tokens) == ("obj", 1, 2)
