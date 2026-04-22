"""`brain mcp` — install/uninstall/selftest/status for the Claude Desktop integration.

Thin CLI wrapper over ``brain_core.integrations.claude_desktop``. Four commands:

* ``install`` — write the ``mcpServers.brain`` entry into Claude Desktop's
  config, with a timestamped backup of any prior file. Destructive enough that
  we require a typed ``"yes"`` confirmation unless ``--yes`` is passed.
* ``uninstall`` — remove the entry, same confirmation flow.
* ``status`` — show the current ``VerifyResult`` without spawning anything.
* ``selftest`` — verify config, then spawn ``brain-mcp`` as a subprocess via
  the MCP SDK's stdio client and round-trip a ``tools/list`` request.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

import typer
from brain_core.integrations.claude_desktop import (
    detect_config_path,
    install,
    read_config,
    uninstall,
    verify,
)
from rich.console import Console

mcp_app = typer.Typer(
    name="mcp",
    help="Manage the brain MCP server integration with Claude Desktop.",
    no_args_is_help=True,
)


# Module-level singleton so ruff/B008 is happy — see brain_cli.commands.patches.
_DEFAULT_VAULT = Path.home() / "Documents" / "brain"

# Tool count registered by ``brain_mcp.server.create_server``. Plan 04 Task 19
# brought the count to 18; Plan 07 Task 4 added 4 more (recent_ingests,
# create_domain, rename_domain, budget_override) → 22; Plan 07 Task 16's
# support tool (``brain_get_pending_patch``) → 23; Plan 07 Task 20's
# ``brain_fork_thread`` (Fork dialog) → 24. Plan 07 Task 25 sub-task A added
# the ten remaining sweep tools (mcp_install, mcp_uninstall, mcp_status,
# mcp_selftest, set_api_key, ping_llm, backup_create, backup_list,
# backup_restore, delete_domain) → 34. ``selftest`` checks for at least this
# many tools so a botched registration surfaces as a failure rather than a
# silent pass.
_EXPECTED_TOOL_COUNT = 34


def _resolve_brain_mcp_command() -> str:
    """Return the command path to use for ``brain-mcp`` in the Claude Desktop config.

    ``shutil.which`` resolves both ``brain-mcp`` (POSIX) and ``brain-mcp.exe``
    (Windows) automatically — no platform branching needed here.
    """
    resolved = shutil.which("brain-mcp")
    if resolved:
        return resolved
    # Fallback: invoke via `python -m brain_mcp`. Use sys.executable to ensure
    # the right Python; arg list is set by _resolve_brain_mcp_args().
    return sys.executable


def _resolve_brain_mcp_args() -> list[str]:
    if shutil.which("brain-mcp"):
        return []
    return ["-m", "brain_mcp"]


@mcp_app.command("install")
def install_cmd(
    vault: Path = typer.Option(  # noqa: B008
        _DEFAULT_VAULT,
        "--vault",
        help="Vault root directory.",
    ),
    domains: str = typer.Option(
        "research,work",
        "--domains",
        help="Comma-separated allowed domains.",
    ),
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Claude Desktop config path (auto-detected if omitted).",
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip typed confirmation."),
) -> None:
    """Install the brain MCP server into Claude Desktop's config."""
    console = Console()
    target = config_path or detect_config_path()
    command = _resolve_brain_mcp_command()
    args = _resolve_brain_mcp_args()
    env = {"BRAIN_VAULT_ROOT": str(vault), "BRAIN_ALLOWED_DOMAINS": domains}

    console.print(f"Installing brain MCP server into [bold]{target}[/bold]")
    console.print(f"  command: {command}")
    console.print(f"  args: {args}")
    console.print(f"  env: {env}")

    if not yes:
        confirm = typer.prompt('Type "yes" to proceed')
        if confirm != "yes":
            typer.echo("aborted")
            raise typer.Exit(code=1)

    result = install(
        config_path=target,
        command=command,
        args=args,
        env=env,
    )
    if result.backup_path:
        console.print(f"[dim]backup saved at {result.backup_path}[/dim]")
    console.print(f"[green]installed[/green] at {result.config_path}")


@mcp_app.command("uninstall")
def uninstall_cmd(
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Claude Desktop config path (auto-detected if omitted).",
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip typed confirmation."),
) -> None:
    """Remove the brain MCP server from Claude Desktop's config."""
    console = Console()
    target = config_path or detect_config_path()

    console.print(f"Uninstalling brain MCP server from [bold]{target}[/bold]")
    if not yes:
        confirm = typer.prompt('Type "yes" to proceed')
        if confirm != "yes":
            typer.echo("aborted")
            raise typer.Exit(code=1)

    result = uninstall(config_path=target)
    if result.removed:
        if result.backup_path:
            console.print(f"[dim]backup saved at {result.backup_path}[/dim]")
        console.print("[green]uninstalled[/green]")
    else:
        console.print("[yellow]no brain entry found in config[/yellow]")


@mcp_app.command("status")
def status_cmd(
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Claude Desktop config path (auto-detected if omitted).",
    ),
) -> None:
    """Report the current installation status."""
    console = Console()
    target = config_path or detect_config_path()
    result = verify(config_path=target)
    console.print(f"config path: {target}")
    console.print(f"config_exists: {result.config_exists}")
    console.print(f"entry_present: {result.entry_present}")
    console.print(f"executable_resolves: {result.executable_resolves}")
    if result.command:
        console.print(f"command: {result.command}")
    if not (result.config_exists and result.entry_present and result.executable_resolves):
        console.print("[yellow]brain MCP not fully installed — run `brain mcp install`[/yellow]")


@mcp_app.command("selftest")
def selftest_cmd(
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Claude Desktop config path (auto-detected if omitted).",
    ),
) -> None:
    """Round-trip test: verify config, spawn the MCP server subprocess, list tools."""
    console = Console()
    target = config_path or detect_config_path()

    # Check 1: verify config.
    v = verify(config_path=target)
    console.print("[1/3] config verification: ", end="")
    if not (v.config_exists and v.entry_present and v.executable_resolves):
        console.print("[red]FAIL[/red]")
        console.print(
            f"  config_exists={v.config_exists}, entry_present={v.entry_present}, "
            f"executable_resolves={v.executable_resolves}"
        )
        raise typer.Exit(code=1)
    console.print("[green]OK[/green]")

    # Check 2: subprocess round-trip. Pass the env dict from the Claude Desktop
    # config so the subprocess gets the same BRAIN_VAULT_ROOT / allowed-domains
    # the user installed — otherwise selftest silently tests against a
    # different vault than the one Claude Desktop uses.
    console.print("[2/3] subprocess tools/list round-trip: ", end="")
    try:
        tool_count = asyncio.run(_subprocess_tools_list(config_path=target))
    except Exception as exc:
        console.print(f"[red]FAIL[/red] ({exc})")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]OK[/green] ({tool_count} tools)")

    # Check 3: tool count matches expected.
    console.print("[3/3] tool count sanity: ", end="")
    if tool_count < _EXPECTED_TOOL_COUNT:
        console.print(f"[red]FAIL[/red] (expected >= {_EXPECTED_TOOL_COUNT}, got {tool_count})")
        raise typer.Exit(code=1)
    console.print("[green]OK[/green]")

    console.print("\n[bold green]selftest passed[/bold green]")


async def _subprocess_tools_list(*, config_path: Path, server_name: str = "brain") -> int:
    """Spawn brain-mcp as a subprocess, run tools/list via the MCP SDK, return the tool count.

    The env dict passed to the subprocess comes from the Claude Desktop
    config so selftest exercises the same BRAIN_VAULT_ROOT / allowed-domains
    the user installed. Falls back to the default vault location if the
    config entry has no env dict (unusual but handled).
    """
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    # Read env out of the installed config entry. verify() has already checked
    # the entry exists, but guard defensively in case the selftest flow changes.
    config = read_config(config_path)
    entry = config.get("mcpServers", {}).get(server_name, {})
    env = dict(entry.get("env") or {})
    if "BRAIN_VAULT_ROOT" not in env:
        env["BRAIN_VAULT_ROOT"] = str(Path.home() / "Documents" / "brain")

    params = StdioServerParameters(
        command=_resolve_brain_mcp_command(),
        args=_resolve_brain_mcp_args(),
        env=env,
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.list_tools()
        return len(result.tools)
