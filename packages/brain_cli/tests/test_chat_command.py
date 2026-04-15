"""Tests for brain_cli.commands.chat (slash parser + help surface)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from brain_cli.app import app
from brain_cli.commands.chat import _handle_slash_command
from brain_core.chat.types import ChatMode
from rich.console import Console
from typer.testing import CliRunner


class _FakeSession:
    """Minimal stand-in for ChatSession exposing the mutators the slash parser calls."""

    def __init__(self) -> None:
        self.mode = ChatMode.ASK
        self.domains: tuple[str, ...] = ("research",)
        self.open_doc: Path | None = None

    def switch_mode(self, new_mode: ChatMode) -> None:
        self.mode = new_mode

    def switch_scope(self, new_domains: tuple[str, ...]) -> None:
        self.domains = new_domains

    def set_open_doc(self, path: Path | None) -> None:
        self.open_doc = path


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return (
        Console(file=buf, force_terminal=False, width=120, color_system=None),
        buf,
    )


def test_chat_command_help() -> None:
    result = CliRunner().invoke(app, ["chat", "--help"])
    assert result.exit_code == 0, result.output
    assert "chat" in result.output.lower()
    assert "--mode" in result.output
    assert "--domain" in result.output
    assert "--vault" in result.output


def test_slash_quit_exits() -> None:
    session = _FakeSession()
    console, _ = _make_console()
    assert _handle_slash_command("/quit", session, console) is True  # type: ignore[arg-type]
    assert _handle_slash_command("/q", session, console) is True  # type: ignore[arg-type]
    assert _handle_slash_command("/exit", session, console) is True  # type: ignore[arg-type]


def test_slash_mode_switches() -> None:
    session = _FakeSession()
    console, buf = _make_console()
    assert (
        _handle_slash_command("/mode brainstorm", session, console) is False  # type: ignore[arg-type]
    )
    assert session.mode == ChatMode.BRAINSTORM
    assert "brainstorm" in buf.getvalue()


def test_slash_mode_unknown_prints_error() -> None:
    session = _FakeSession()
    console, buf = _make_console()
    assert _handle_slash_command("/mode warp", session, console) is False  # type: ignore[arg-type]
    assert session.mode == ChatMode.ASK
    assert "unknown mode" in buf.getvalue()


def test_slash_scope_updates_and_warns_personal() -> None:
    session = _FakeSession()
    console, buf = _make_console()
    assert (
        _handle_slash_command("/scope work, personal", session, console) is False  # type: ignore[arg-type]
    )
    assert session.domains == ("work", "personal")
    assert "personal" in buf.getvalue()


def test_slash_file_sets_and_clears_open_doc() -> None:
    session = _FakeSession()
    console, _ = _make_console()
    assert (
        _handle_slash_command("/file research/notes.md", session, console) is False  # type: ignore[arg-type]
    )
    assert session.open_doc == Path("research/notes.md")

    assert _handle_slash_command("/file", session, console) is False  # type: ignore[arg-type]
    assert session.open_doc is None


def test_slash_unknown_command() -> None:
    session = _FakeSession()
    console, buf = _make_console()
    assert _handle_slash_command("/teapot short stout", session, console) is False  # type: ignore[arg-type]
    assert "unknown command" in buf.getvalue()


def test_chat_command_errors_on_missing_vault(tmp_path: Any) -> None:
    missing = tmp_path / "does-not-exist"
    result = CliRunner().invoke(app, ["chat", "--vault", str(missing)])
    assert result.exit_code == 1
    assert "vault not found" in result.output
