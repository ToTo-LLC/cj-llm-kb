"""``brain patches`` \u2014 minimal CLI for inspecting and applying staged patches."""

from __future__ import annotations

from pathlib import Path

import typer
from brain_core.chat.pending import PendingPatchStore
from brain_core.vault.writer import VaultWriter

patches_app = typer.Typer(
    name="patches",
    help="Manage staged chat patches.",
    no_args_is_help=True,
)

_DEFAULT_VAULT = Path.home() / "Documents" / "brain"


@patches_app.command("list")
def list_patches(
    vault: Path = typer.Option(  # noqa: B008
        _DEFAULT_VAULT, "--vault", help="Vault root directory."
    ),
) -> None:
    """List pending patches."""
    store = PendingPatchStore(vault / ".brain" / "pending")
    envelopes = store.list()
    if not envelopes:
        typer.echo("(no pending patches)")
        return

    typer.echo(f"{len(envelopes)} pending patch(es):")
    for env in envelopes:
        reason = (env.reason[:60] + "...") if len(env.reason) > 60 else env.reason
        typer.echo(
            f"  {env.patch_id}  {env.mode.value:<10}  {env.tool:<14}  {env.target_path}  ({reason})"
        )


@patches_app.command("apply")
def apply_patch(
    patch_id: str = typer.Argument(..., help="Patch ID to apply."),
    yes: bool = typer.Option(False, "--yes", help="Skip typed confirmation."),
    vault: Path = typer.Option(  # noqa: B008
        _DEFAULT_VAULT, "--vault", help="Vault root directory."
    ),
) -> None:
    """Apply a staged patch to the vault via VaultWriter."""
    store = PendingPatchStore(vault / ".brain" / "pending")
    envelope = store.get(patch_id)
    if envelope is None:
        typer.echo(f"error: patch {patch_id!r} not found", err=True)
        raise typer.Exit(code=1)

    if not yes:
        typer.echo(f"About to apply: {envelope.tool} \u2192 {envelope.target_path}")
        typer.echo(f"Reason: {envelope.reason}")
        confirm = typer.prompt('Type "yes" to apply')
        if confirm != "yes":
            typer.echo("aborted")
            raise typer.Exit(code=1)

    first_part = envelope.target_path.parts[0] if envelope.target_path.parts else ""
    if not first_part:
        typer.echo("error: cannot derive domain from target path", err=True)
        raise typer.Exit(code=1)

    writer = VaultWriter(vault_root=vault)
    # Bare Exception catch: surface any writer failure (ScopeError,
    # PatchTooLargeError, FileExistsError, OSError, ...) as a clean exit-1
    # rather than a traceback. Users on the CLI should see a one-line error.
    try:
        receipt = writer.apply(envelope.patchset, allowed_domains=(first_part,))
    except Exception as exc:
        typer.echo(f"error applying patch: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store.mark_applied(patch_id)
    typer.echo(f"applied {patch_id} (undo_id={receipt.undo_id})")


@patches_app.command("reject")
def reject_patch(
    patch_id: str = typer.Argument(..., help="Patch ID to reject."),
    reason: str = typer.Option(..., "--reason", help="Reason for rejection."),
    vault: Path = typer.Option(  # noqa: B008
        _DEFAULT_VAULT, "--vault", help="Vault root directory."
    ),
) -> None:
    """Reject a staged patch \u2014 moves it to ``.brain/pending/rejected/``."""
    store = PendingPatchStore(vault / ".brain" / "pending")
    try:
        store.reject(patch_id, reason=reason)
    except KeyError:
        typer.echo(f"error: patch {patch_id!r} not found", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"rejected {patch_id}")
