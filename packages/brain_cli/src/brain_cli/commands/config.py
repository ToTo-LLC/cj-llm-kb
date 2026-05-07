"""``brain config`` — Typer subcommand for config-related ops (Plan 16 T41).

Currently exposes ``migrate`` for the legacy → new-shape ``config.json``
rollover (D31). Future config-related ops (e.g. ``brain config show``,
``brain config validate``) can land here without growing yet another
top-level CLI verb.

Exit codes for ``brain config migrate``:

  * 0 — file rewritten OR already in the new shape (no-op).
  * 1 — config file not found at ``path``.
  * 2 — file exists but cannot be parsed (malformed JSON / wrong shape).

The CLI is a thin wrapper over
:func:`brain_core.config.migrate.migrate_config_file` — every behavior
that matters is pinned by ``brain_core/tests/config/test_migrate.py``.
This module's tests cover the user-facing CLI surface (exit codes,
stdout / stderr framing, default-path resolution).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from brain_core.config.migrate import migrate_config_file

app = typer.Typer(
    name="config",
    help="Manage your brain config.",
    no_args_is_help=True,
)


def _default_config_path() -> Path:
    """Default vault config location: ``~/Documents/brain/.brain/config.json``.

    Mirrors the patches command's ``_DEFAULT_VAULT`` shape — we don't
    consult ``$BRAIN_VAULT_ROOT`` here because migrate is a one-shot
    operation that users typically run BEFORE the env var is in place
    (e.g. as part of an upgrade dance). Users with a non-default vault
    pass ``brain config migrate <path>`` explicitly.
    """
    return Path.home() / "Documents" / "brain" / ".brain" / "config.json"


@app.command("migrate")
def migrate(
    path: Path | None = typer.Argument(  # noqa: B008
        None,
        help=(
            "Path to config.json (default: "
            "~/Documents/brain/.brain/config.json)."
        ),
    ),
) -> None:
    """Migrate an old-shape ``config.json`` to the current schema.

    Backs up the original to ``<path>.pre-migrate.bak`` (or ``.bak.1`` /
    ``.bak.2`` / ... if a prior backup exists) BEFORE writing.
    Idempotent: re-runs on an already-migrated file are no-ops and do
    not create new backup files.
    """
    target = path if path is not None else _default_config_path()

    try:
        result = migrate_config_file(target)
    except FileNotFoundError:
        typer.echo(f"Error: config file not found: {target}", err=True)
        raise typer.Exit(code=1) from None
    except json.JSONDecodeError as exc:
        typer.echo(
            f"Error: failed to parse {target}: {exc}",
            err=True,
        )
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        # Non-dict top-level: distinguished from JSONDecodeError but
        # surfaced under the same exit code (2 = "exists but malformed").
        typer.echo(
            f"Error: failed to parse {target}: {exc}",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    if not result.migrated:
        typer.echo(f"No migration needed; {target} is already up to date.")
        return

    typer.echo(f"Migrated {target}")
    typer.echo(f"  Backup: {result.backup_path}")
    for change in result.changes:
        typer.echo(f"  Change: {change}")
