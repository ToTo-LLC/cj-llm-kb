"""``brain doctor`` — plain-English health report across 10 checks.

Plan 08 Task 4. Prints a status line per check (``[PASS]`` / ``[WARN]`` /
``[INFO]`` / ``[FAIL]``), a ``Fix:`` line under any warn/fail, and a
one-line summary. Colorizes output on a TTY (rich is already a dep).
``--json`` mode emits a single JSON array for scripting.

Exit code: 0 if no FAIL, 1 if any FAIL. WARN and INFO are non-fatal.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from brain_cli.runtime import checks


def _collect_results(
    install_dir: Path,
    vault_root: Path,
) -> list[checks.CheckResult]:
    """Run all 10 checks in display order. Never raises."""
    return [
        checks.check_uv(),
        checks.check_install_dir(install_dir=install_dir),
        checks.check_venv(install_dir=install_dir),
        checks.check_node(install_dir=install_dir),
        checks.check_ports(),
        checks.check_vault(vault_root=vault_root),
        checks.check_token(vault_root=vault_root),
        checks.check_config(vault_root=vault_root),
        checks.check_sqlite(vault_root=vault_root),
        checks.check_ui_bundle(install_dir=install_dir),
    ]


_STATUS_STYLE: dict[str, str] = {
    "pass": "green",
    "info": "cyan",
    "warn": "yellow",
    "fail": "red",
}

_STATUS_LABEL: dict[str, str] = {
    "pass": "[PASS]",
    "info": "[INFO]",
    "warn": "[WARN]",
    "fail": "[FAIL]",
}


def _render_human(results: list[checks.CheckResult], console: Console) -> None:
    """Print the pretty, TTY-aware report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    console.print(f"brain doctor  · {timestamp}", style="bold")
    console.print("")

    for r in results:
        label = _STATUS_LABEL[r.status]
        style = _STATUS_STYLE[r.status]
        # Render the label in color; leave the message neutral so colors stay readable.
        console.print(f"[{style}]{label}[/{style}] {r.message}")
        if r.fix_hint and r.status in {"warn", "fail"}:
            console.print(f"       Fix: {r.fix_hint}")

    # "passed" here means "not failing" — PASS, INFO, and WARN are all
    # non-blocking. Only FAIL subtracts from the numerator so users see a
    # clean "10/10" when nothing's broken (per the Plan 08 spec output).
    passed = sum(1 for r in results if r.status != "fail")
    total = len(results)
    any_fail = any(r.status == "fail" for r in results)
    any_warn = any(r.status == "warn" for r in results)

    if any_fail:
        verdict = "see [FAIL] lines above for next actions."
        verdict_style = "red"
    elif any_warn:
        verdict = "warnings above are worth a second look; nothing blocking."
        verdict_style = "yellow"
    else:
        verdict = "you're good to go. Run `brain start` to launch."
        verdict_style = "green"

    console.print("")
    console.print(f"{passed}/{total} checks passed · [{verdict_style}]{verdict}[/{verdict_style}]")


def _resolve_install_dir() -> Path:
    return checks.default_install_dir()


def _resolve_vault_root() -> Path:
    return checks.default_vault_root()


def doctor(
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
    install: Path | None = typer.Option(  # noqa: B008
        None,
        "--install",
        help="Install dir (defaults to $BRAIN_INSTALL_DIR or platform default).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON array of check results (no colors, no summary).",
    ),
) -> None:
    """Run 10 health checks + print a plain-English report.

    Exit 0 if everything passes (or only WARN/INFO). Exit 1 if any check
    FAILs so CI + install scripts can gate on it.
    """
    install_dir = install or _resolve_install_dir()
    vault_root = vault or _resolve_vault_root()

    results = _collect_results(install_dir=install_dir, vault_root=vault_root)

    if as_json:
        # Plain stdout, no color, single JSON array.
        typer.echo(json.dumps([r.to_dict() for r in results]))
    else:
        console = Console(
            # Typer's CliRunner captures stdout — use ``force_terminal=False``
            # so we don't paint ANSI into test output. Real TTYs autodetect.
            force_terminal=sys.stdout.isatty() or None,
            highlight=False,
        )
        _render_human(results, console)

    if any(r.status == "fail" for r in results):
        raise typer.Exit(code=1)
