"""``brain chat`` \u2014 interactive chat command against a brain vault."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from brain_core.chat.types import ChatMode
from rich.console import Console

from brain_cli.rendering.stream import StreamRenderer
from brain_cli.session_factory import build_session

if TYPE_CHECKING:
    from brain_core.chat.session import ChatSession


_DEFAULT_VAULT = Path.home() / "Documents" / "brain"


def chat(
    mode: ChatMode = typer.Option(  # noqa: B008
        ChatMode.ASK, "--mode", "-m", help="Chat mode: ask, brainstorm, or draft."
    ),
    domain: list[str] = typer.Option(  # noqa: B008
        ["research"], "--domain", "-d", help="Active domain(s); repeat flag for multiple."
    ),
    open_doc: Path | None = typer.Option(  # noqa: B008
        None, "--open", help="Open document path (vault-relative) for Draft mode."
    ),
    model: str = typer.Option(
        "claude-sonnet-4-6", "--model", help="Claude model to use for the main loop."
    ),
    vault: Path = typer.Option(  # noqa: B008
        _DEFAULT_VAULT, "--vault", help="Vault root directory."
    ),
) -> None:
    """Start an interactive chat session against the brain vault."""
    if not vault.exists():
        typer.echo(f"error: vault not found at {vault}", err=True)
        raise typer.Exit(code=1)

    try:
        session = build_session(
            mode=mode,
            domains=tuple(domain),
            open_doc=open_doc,
            model=model,
            vault_root=vault,
        )
    except RuntimeError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    asyncio.run(_run_chat_loop(session))


async def _run_chat_loop(session: ChatSession) -> None:
    """Interactive REPL. Imports prompt_toolkit lazily so ``brain --version`` stays fast."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    console = Console()
    renderer = StreamRenderer(console=console)
    prompt_session: PromptSession[str] = PromptSession(history=InMemoryHistory())

    console.print(
        f"[bold]brain chat[/bold] \u00b7 mode={session.config.mode.value} \u00b7 "
        f"scope={','.join(session.config.domains)} \u00b7 thread={session.thread_id}"
    )
    console.print(
        "[dim]Type a message, or /quit to exit. Slash commands: /mode, /scope, /file, /quit.[/dim]"
    )

    while True:
        try:
            user_message = await prompt_session.prompt_async("> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]aborted[/dim]")
            break

        user_message = user_message.strip()
        if not user_message:
            continue

        if user_message.startswith("/"):
            if _handle_slash_command(user_message, session, console):
                break
            continue

        try:
            await renderer.render_stream(session.turn(user_message))
        except Exception as exc:
            console.print(f"[red]error: {type(exc).__name__}: {exc}[/red]")


def _handle_slash_command(
    command: str,
    session: ChatSession,
    console: Console,
) -> bool:
    """Handle /mode, /scope, /file, /quit. Returns True if the loop should exit."""
    parts = command.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if verb in ("/quit", "/q", "/exit"):
        return True

    if verb == "/mode":
        if not arg:
            console.print("[yellow]usage: /mode ask|brainstorm|draft[/yellow]")
            return False
        try:
            new_mode = ChatMode(arg.strip().lower())
        except ValueError:
            console.print(f"[red]unknown mode: {arg}[/red]")
            return False
        session.switch_mode(new_mode)
        console.print(f"[dim]mode \u2192 {new_mode.value}[/dim]")
        return False

    if verb == "/scope":
        if not arg:
            console.print("[yellow]usage: /scope domain1,domain2[/yellow]")
            return False
        new_domains = tuple(d.strip() for d in arg.split(",") if d.strip())
        if not new_domains:
            console.print("[yellow]no domains given[/yellow]")
            return False
        if "personal" in new_domains:
            console.print("[yellow]warning: scope includes 'personal'[/yellow]")
        session.switch_scope(new_domains)
        console.print(f"[dim]scope \u2192 {','.join(new_domains)}[/dim]")
        return False

    if verb == "/file":
        if not arg:
            session.set_open_doc(None)
            console.print("[dim]open doc cleared[/dim]")
            return False
        session.set_open_doc(Path(arg.strip()))
        console.print(f"[dim]open doc \u2192 {arg}[/dim]")
        return False

    console.print(f"[yellow]unknown command: {verb}[/yellow]")
    return False
