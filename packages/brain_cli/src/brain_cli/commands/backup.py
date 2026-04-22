"""``brain backup`` — create a manual vault snapshot.

Plan 08 Task 9. Thin wrapper over :func:`brain_core.backup.create_snapshot`
(Plan 07 Task 25A). The CLI surface keeps the core call honest: we
validate the vault exists up front and surface any backup error as plain
English rather than a traceback.

Exit codes:
    0 — snapshot written, path + size printed.
    1 — vault missing OR ``create_snapshot`` raised.

``--json`` mode emits a single JSON object with the :class:`BackupMeta`
fields (path stringified, ``created_at`` as ISO-8601) so scripts and
install smoke tests can parse the result without scraping the pretty
output.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer
from brain_core.backup import BackupMeta, create_snapshot
from rich.console import Console

from brain_cli.runtime import checks

__all__ = ["backup", "create_snapshot"]


_BYTES_UNITS = ("B", "KB", "MB", "GB", "TB")


def _format_size(size_bytes: int) -> str:
    """Human-readable size with one decimal past KB (``"2.4 MB"``)."""
    size = float(size_bytes)
    for unit in _BYTES_UNITS:
        if size < 1024 or unit == _BYTES_UNITS[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    # Unreachable — the loop always returns on its last iteration.
    return f"{size_bytes} B"


def _meta_to_json(meta: BackupMeta) -> dict[str, Any]:
    """Convert a :class:`BackupMeta` into a JSON-serializable dict."""
    payload = asdict(meta)
    payload["path"] = str(meta.path)
    payload["created_at"] = meta.created_at.isoformat()
    return payload


def backup(
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
    trigger: str = typer.Option(
        "manual",
        "--trigger",
        help="Backup trigger label recorded in the filename. Only 'manual' "
        "is allowed from the CLI; scheduled + pre-import triggers are "
        "owned by the supervisor.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON object with the BackupMeta fields instead of the "
        "pretty summary.",
    ),
) -> None:
    """Create a tarball snapshot of the vault under ``<vault>/.brain/backups/``.

    The snapshot is a gzip-compressed tarball; ephemeral paths
    (``.brain/run/``, ``.brain/logs/``, ``.brain/secrets.env``) are
    excluded. Nothing on disk is mutated besides the new tarball — the
    vault itself is untouched.
    """
    if trigger != "manual":
        # Keep the CLI surface conservative: manual-only. The scheduler
        # (daily) and bulk-import safety net (pre_bulk_import) are owned
        # by the supervisor, not typed by humans at a prompt.
        typer.echo(
            f"Unsupported trigger {trigger!r}. Only 'manual' is allowed "
            "from the CLI. Scheduled backups are handled by the "
            "supervisor.",
            err=True,
        )
        raise typer.Exit(code=1)

    vault_root = (vault or checks.default_vault_root()).expanduser()

    if not vault_root.exists():
        typer.echo(
            f"No vault found at {vault_root}. Run 'brain doctor' to diagnose.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        meta = create_snapshot(vault_root, trigger="manual")
    except Exception as exc:
        typer.echo(f"Backup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(json.dumps(_meta_to_json(meta)))
        return

    # Use Rich only for the colored header; plain ``typer.echo`` for the
    # detail lines so long paths never wrap mid-string and remain greppable
    # by both humans and shell scripts.
    console = Console(highlight=False, soft_wrap=True)
    console.print("[green]✓ Backup created[/green]")
    typer.echo(f"  Path: {meta.path}")
    typer.echo(f"  Size: {_format_size(meta.size_bytes)}")
    typer.echo(f"  Files: {meta.file_count}")
    typer.echo(f"  Trigger: {meta.trigger}")
