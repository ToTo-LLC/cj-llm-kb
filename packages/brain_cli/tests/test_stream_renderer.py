"""Tests for brain_cli.rendering.stream.StreamRenderer."""

from __future__ import annotations

from io import StringIO

from brain_cli.rendering.stream import StreamRenderer
from brain_core.chat.types import ChatEvent, ChatEventKind
from rich.console import Console


def _make_renderer() -> tuple[StreamRenderer, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120, color_system=None)
    return StreamRenderer(console=console), buf


def test_renders_delta() -> None:
    renderer, buf = _make_renderer()
    renderer.render(ChatEvent(kind=ChatEventKind.DELTA, data={"text": "hello world"}))
    out = buf.getvalue()
    assert "hello world" in out
    assert "assistant:" in out


def test_renders_tool_call_panel() -> None:
    renderer, buf = _make_renderer()
    renderer.render(
        ChatEvent(
            kind=ChatEventKind.TOOL_CALL,
            data={"name": "search_vault", "args": {"query": "foo"}},
        )
    )
    out = buf.getvalue()
    assert "tool call" in out
    assert "search_vault" in out


def test_renders_patch_proposed_panel() -> None:
    renderer, buf = _make_renderer()
    renderer.render(
        ChatEvent(
            kind=ChatEventKind.PATCH_PROPOSED,
            data={"patch_id": "abc123", "target_path": "research/notes/foo.md"},
        )
    )
    out = buf.getvalue()
    assert "abc123" in out
    assert "research/notes/foo.md" in out
    assert "patch" in out.lower()


def test_renders_turn_end_with_cost() -> None:
    renderer, buf = _make_renderer()
    renderer.render(
        ChatEvent(
            kind=ChatEventKind.COST_UPDATE,
            data={"session_cost_usd": 0.0123},
        )
    )
    renderer.render(ChatEvent(kind=ChatEventKind.TURN_END, data={"cost_usd": 0.0042}))
    out = buf.getvalue()
    assert "0.0042" in out
    assert "0.0123" in out


def test_renders_error_panel() -> None:
    renderer, buf = _make_renderer()
    renderer.render(ChatEvent(kind=ChatEventKind.ERROR, data={"message": "boom went the dynamite"}))
    out = buf.getvalue()
    assert "boom went the dynamite" in out
    assert "error" in out.lower()
