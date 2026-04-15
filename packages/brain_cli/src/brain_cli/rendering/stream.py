"""Rich terminal renderer for ChatSession event streams.

StreamRenderer consumes ``ChatEvent`` values from ``ChatSession.turn()`` and maps
each event kind to a Rich Console output: DELTA is streamed inline, tool events
become dim panels, PATCH_PROPOSED becomes a yellow panel, and TURN_END emits a
dim cost summary line.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from brain_core.chat.types import ChatEvent, ChatEventKind
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class StreamRenderer:
    """Render ``ChatEvent`` values to a Rich ``Console``."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._in_assistant_text = False
        self._cumulative_cost = 0.0

    def render(self, event: ChatEvent) -> None:
        """Render a single event. Safe to call repeatedly."""
        kind = event.kind
        data = event.data

        if kind == ChatEventKind.DELTA:
            if not self._in_assistant_text:
                self.console.print("\n[bold cyan]assistant:[/bold cyan] ", end="")
                self._in_assistant_text = True
            self.console.print(str(data.get("text", "")), end="")
            return

        if kind == ChatEventKind.TOOL_CALL:
            self._end_assistant_text()
            name = data.get("name", "?")
            args = data.get("args", {})
            self.console.print(
                Panel(
                    Text(f"{name}({args})", style="dim"),
                    title="tool call",
                    border_style="dim",
                    expand=False,
                )
            )
            return

        if kind == ChatEventKind.TOOL_RESULT:
            text = str(data.get("text", ""))
            if len(text) > 500:
                text = text[:500] + "..."
            error = bool(data.get("error", False))
            style = "red" if error else "dim"
            self.console.print(
                Panel(
                    Text(text, style=style),
                    title="tool result" + (" (error)" if error else ""),
                    border_style=style,
                    expand=False,
                )
            )
            return

        if kind == ChatEventKind.PATCH_PROPOSED:
            self._end_assistant_text()
            patch_id = data.get("patch_id", "?")
            target = data.get("target_path", "?")
            self.console.print(
                Panel(
                    Text(f"[staged] patch: {target} [{patch_id}]", style="yellow"),
                    title="patch proposed",
                    border_style="yellow",
                    expand=False,
                )
            )
            return

        if kind == ChatEventKind.COST_UPDATE:
            self._cumulative_cost = float(data.get("session_cost_usd", self._cumulative_cost))
            return

        if kind == ChatEventKind.TURN_END:
            self._end_assistant_text()
            turn_cost = float(data.get("cost_usd", 0.0))
            turn_error = data.get("error")
            if turn_error:
                self.console.print(f"[red][turn error: {turn_error}][/red]")
            else:
                self.console.print(
                    f"[dim]cost +${turn_cost:.4f} \u00b7 total ${self._cumulative_cost:.4f}[/dim]"
                )
            return

        if kind == ChatEventKind.ERROR:
            self._end_assistant_text()
            message = str(data.get("message", "unknown error"))
            self.console.print(
                Panel(
                    Text(message, style="red"),
                    title="error",
                    border_style="red",
                    expand=False,
                )
            )
            return

    def _end_assistant_text(self) -> None:
        if self._in_assistant_text:
            self.console.print()
            self._in_assistant_text = False

    async def render_stream(self, events: AsyncIterator[ChatEvent]) -> None:
        """Render an entire async event stream until it completes."""
        async for event in events:
            self.render(event)
        self._end_assistant_text()
