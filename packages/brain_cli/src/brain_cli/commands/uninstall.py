"""``brain uninstall`` — Plan 08 Task 6.

Spec §9 §Uninstall. Four prompt flow; vault is sacred.

Prompts (interactive mode):

1. ``Remove brain code at <install>?`` — typed-confirm ``UNINSTALL``.
2. ``Remove Claude Desktop MCP config entry?`` — only if the entry is
   currently present.
3. ``Keep vault at <vault>?`` — default Y.
4. (only if 3 said ``n``) ``Type DELETE-VAULT to permanently remove …``.
5. (only if vault kept) ``Remove backups at <vault>/.brain/backups/?``
   — default Y.

Removal order, on the success path:

a. Uninstall Claude Desktop MCP entry (reversible — user can re-add via
   ``brain mcp install``).
b. Remove backups (if opted in).
c. Remove code install dir.
d. Remove shim from PATH location.
e. If ``--delete-vault``: remove vault root.

Every step is wrapped in a best-effort try/except so a partial failure
doesn't leave the user without a recovery path. Errors accumulate and
are surfaced in a final summary line.

Non-interactive mode: ``--yes`` skips every prompt. ``--delete-vault``
is still required to remove the vault (belt + suspenders, per the plan).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import typer
from brain_core.integrations import claude_desktop

from brain_cli.runtime import paths, pidfile, supervisor

# Typed-confirm strings. Kept as module constants so the tests can
# reference them and future translators have one place to edit.
_CONFIRM_CODE = "UNINSTALL"
_CONFIRM_VAULT = "DELETE-VAULT"

# shutil.rmtree retry params for Windows handle-linger.
_RMTREE_RETRIES = 3
_RMTREE_BACKOFF_S = 0.5


@dataclass
class _Outcome:
    """Accumulated success / failure log for the final summary.

    Each field is either a message string (on that action happening), a
    ``None`` (action skipped), or a tuple ``(kind, err)`` where ``kind``
    is a human label and ``err`` the exception text.
    """

    mcp_removed: str | None = None
    code_removed: str | None = None
    shim_removed: str | None = None
    app_wrapper_removed: str | None = None
    vault_action: str | None = None  # "preserved" / "removed"
    backups_removed: str | None = None
    errors: list[tuple[str, str]] = field(default_factory=list)


def _resolve_shim_paths() -> list[Path]:
    """Platform-specific shim paths. All optional — absent paths are fine.

    Order matters for the final summary — the first match wins when we
    report "Shim removed (<path>)".
    """
    override = os.environ.get("BRAIN_SHIM_DIR")
    if override:
        base = Path(override)
        shim = base / ("brain.cmd" if sys.platform == "win32" else "brain")
        return [shim]
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return [Path(localappdata) / "Microsoft" / "WindowsApps" / "brain.cmd"]
        return [Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "brain.cmd"]
    return [Path.home() / ".local" / "bin" / "brain"]


def _resolve_app_wrapper_path() -> Path | None:
    """Mac-only ``~/Applications/brain.app/`` directory wrapper (Task 9).

    On non-Mac platforms there's nothing analogous to remove. Returns
    ``None`` so callers can skip cleanly.
    """
    if sys.platform != "darwin":
        return None
    return Path.home() / "Applications" / "brain.app"


def _force_rmtree(path: Path) -> None:
    """``shutil.rmtree`` with Windows retry for open-handle races.

    Mirrors the pattern in ``runtime/swap.py`` so both upgrade + uninstall
    tolerate the same transient Windows behavior after a stop. POSIX
    hits the happy path on the first attempt.
    """

    def _on_error(func: object, target: str, _exc: BaseException) -> None:
        # Best-effort chmod + retry: ``__pycache__`` entries sometimes
        # land read-only on Windows.
        with contextlib.suppress(OSError):
            Path(target).chmod(0o700)
        if callable(func):
            with contextlib.suppress(OSError):
                func(target)  # type: ignore[call-arg]

    last_exc: BaseException | None = None
    for attempt in range(_RMTREE_RETRIES):
        try:
            shutil.rmtree(path, onexc=_on_error)  # type: ignore[call-arg]
            return
        except (PermissionError, OSError) as exc:
            last_exc = exc
            if sys.platform != "win32" or attempt == _RMTREE_RETRIES - 1:
                raise
            time.sleep(_RMTREE_BACKOFF_S)
    assert last_exc is not None
    raise last_exc


def _stop_running_daemon(vault_root: Path) -> None:
    """Best-effort ``brain stop`` so we don't fight file locks on Windows.

    Silent when no daemon is running — this command shouldn't print a
    "not running" line during uninstall, that'd be noise.
    """
    pid_file = vault_root / ".brain" / "run" / "brain.pid"
    port_file = vault_root / ".brain" / "run" / "brain.port"
    pid = pidfile.read_pid(pid_file)
    if pid is None or not pidfile.is_alive(pid):
        pidfile.delete_pid(pid_file)
        if port_file.exists():
            with contextlib.suppress(OSError):
                port_file.unlink()
        return
    try:
        supervisor.stop_brain_api(pid)
    finally:
        pidfile.delete_pid(pid_file)
        if port_file.exists():
            with contextlib.suppress(OSError):
                port_file.unlink()


def _mcp_is_installed() -> bool:
    """Return True iff Claude Desktop has a ``brain`` entry right now.

    Swallows every ``claude_desktop`` failure — if we can't detect the
    config (unsupported OS, missing %APPDATA%), we behave as though no
    entry exists and skip the prompt cleanly. The user can always run
    ``brain mcp uninstall`` by hand if they need to.
    """
    try:
        config_path = claude_desktop.detect_config_path()
    except claude_desktop.UnsupportedPlatformError:
        return False
    try:
        result = claude_desktop.verify(config_path=config_path)
    except Exception:
        return False
    return bool(result.entry_present)


def _remove_mcp(outcome: _Outcome) -> None:
    """Remove the ``brain`` MCP entry from Claude Desktop config."""
    try:
        config_path = claude_desktop.detect_config_path()
        claude_desktop.uninstall(config_path=config_path)
    except Exception as exc:  # pragma: no cover - defensive
        outcome.errors.append(("Claude Desktop MCP entry", str(exc)))
        return
    outcome.mcp_removed = "Claude Desktop MCP entry removed"


def _remove_code(install_dir: Path, outcome: _Outcome) -> None:
    """Delete the install dir."""
    if not install_dir.exists():
        outcome.code_removed = f"Code already absent at {install_dir}"
        return
    try:
        _force_rmtree(install_dir)
    except OSError as exc:
        outcome.errors.append((f"code at {install_dir}", str(exc)))
        return
    outcome.code_removed = f"Code removed from {install_dir}"


def _remove_shims(outcome: _Outcome) -> None:
    """Delete platform shim(s). Silent on missing paths."""
    removed: list[str] = []
    for shim in _resolve_shim_paths():
        if not shim.exists():
            continue
        try:
            shim.unlink()
            removed.append(str(shim))
        except OSError as exc:
            outcome.errors.append((f"shim at {shim}", str(exc)))
    if removed:
        outcome.shim_removed = f"Shim removed ({', '.join(removed)})"


def _remove_app_wrapper(outcome: _Outcome) -> None:
    """Mac-only: remove ``~/Applications/brain.app/`` directory wrapper."""
    app_wrapper = _resolve_app_wrapper_path()
    if app_wrapper is None or not app_wrapper.exists():
        return
    try:
        _force_rmtree(app_wrapper)
    except OSError as exc:
        outcome.errors.append((f".app wrapper at {app_wrapper}", str(exc)))
        return
    outcome.app_wrapper_removed = f".app wrapper removed ({app_wrapper})"


def _remove_backups(vault_root: Path, outcome: _Outcome) -> None:
    """Delete ``<vault>/.brain/backups/`` when the vault itself is preserved."""
    backups = vault_root / ".brain" / "backups"
    if not backups.exists():
        return
    try:
        _force_rmtree(backups)
    except OSError as exc:
        outcome.errors.append((f"backups at {backups}", str(exc)))
        return
    outcome.backups_removed = f"Backups removed from {backups}"


def _remove_vault(vault_root: Path, outcome: _Outcome) -> None:
    """Delete the vault. Only reached after typed-confirm or ``--delete-vault``."""
    if not vault_root.exists():
        outcome.vault_action = f"Vault already absent at {vault_root}"
        return
    try:
        _force_rmtree(vault_root)
    except OSError as exc:
        outcome.errors.append((f"vault at {vault_root}", str(exc)))
        return
    outcome.vault_action = f"Vault removed from {vault_root}"


def _print_summary(outcome: _Outcome, *, vault_root: Path, vault_preserved: bool) -> None:
    """Render the final summary block."""
    typer.echo("")
    typer.echo("Uninstall complete.")
    if outcome.mcp_removed:
        typer.echo(f"  [x] {outcome.mcp_removed}")
    if outcome.code_removed:
        typer.echo(f"  [x] {outcome.code_removed}")
    if outcome.shim_removed:
        typer.echo(f"  [x] {outcome.shim_removed}")
    if outcome.app_wrapper_removed:
        typer.echo(f"  [x] {outcome.app_wrapper_removed}")
    if vault_preserved:
        typer.echo(f"  [ ] Vault preserved at {vault_root}")
    elif outcome.vault_action:
        typer.echo(f"  [x] {outcome.vault_action}")
    if outcome.backups_removed:
        typer.echo(f"  [x] {outcome.backups_removed}")

    if outcome.errors:
        typer.echo("")
        typer.echo("Some steps had problems:")
        for label, err in outcome.errors:
            typer.echo(f"  warning: {label}: {err}")
        typer.echo("")
        typer.echo(
            "Manual cleanup: delete any remaining paths listed above by hand. "
            "The uninstall command is safe to re-run."
        )


def uninstall(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip every prompt (still requires --delete-vault to remove vault).",
    ),
    delete_vault: bool = typer.Option(
        False,
        "--delete-vault",
        help="Permanently remove the vault. Required for non-interactive vault removal.",
    ),
    keep_backups: bool = typer.Option(
        False,
        "--keep-backups",
        help="Keep backups under <vault>/.brain/backups/ (default: remove when vault is preserved).",
    ),
    delete_backups: bool = typer.Option(
        False,
        "--delete-backups",
        help="Force backup removal. Default when vault is preserved; redundant otherwise.",
    ),
    install: Path | None = typer.Option(  # noqa: B008
        None,
        "--install",
        help="Install dir (defaults to $BRAIN_INSTALL_DIR or platform default).",
    ),
    vault: Path | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault root (defaults to $BRAIN_VAULT_ROOT or ~/Documents/brain).",
    ),
) -> None:
    """Uninstall brain. The vault is preserved by default."""
    install_dir = install or paths.default_install_dir()
    vault_root = vault or paths.default_vault_root()

    # --- Step 0: stop any running daemon silently ---------------------------
    _stop_running_daemon(vault_root)

    # --- Decision: preserve or remove vault ---------------------------------
    # Resolved BEFORE any destructive action so the summary is consistent.
    vault_preserved: bool
    remove_backups: bool

    if yes:
        # Non-interactive: user's flags speak for themselves.
        vault_preserved = not delete_vault
        if keep_backups:
            remove_backups = False
        elif delete_backups:
            remove_backups = True
        else:
            # Default: remove backups when vault preserved; when vault is
            # being deleted the backups go with it.
            remove_backups = vault_preserved
    else:
        # --- Step 1: interactive code-removal confirmation ------------------
        typer.echo(f"Remove brain code at {install_dir}?")
        reply = typer.prompt(
            f"Type {_CONFIRM_CODE} to confirm (or press Enter to cancel)",
            default="",
            show_default=False,
        )
        if reply != _CONFIRM_CODE:
            typer.echo("uninstall cancelled.")
            raise typer.Exit(code=0)

        # --- Step 2: Claude Desktop MCP prompt ------------------------------
        mcp_installed_at_prompt = _mcp_is_installed()
        do_remove_mcp = False
        if mcp_installed_at_prompt:
            do_remove_mcp = typer.confirm(
                "Remove Claude Desktop MCP config entry?",
                default=True,
            )

        # --- Step 3: vault decision -----------------------------------------
        # ``default=True`` means hitting Enter keeps the vault. This is the
        # safer default — the vault is sacred.
        keep_vault = typer.confirm(
            f"Keep vault at {vault_root}?",
            default=True,
        )
        if keep_vault:
            vault_preserved = True
        else:
            # Step 3b: typed-confirm to actually delete.
            typed = typer.prompt(
                f"Type {_CONFIRM_VAULT} to permanently remove all your notes at {vault_root}",
                default="",
                show_default=False,
            )
            vault_preserved = typed != _CONFIRM_VAULT
            if vault_preserved:
                typer.echo(
                    "Typed confirmation did not match; vault will be preserved."
                )

        # --- Step 4: backups prompt (only if vault preserved) ---------------
        if vault_preserved:
            remove_backups = typer.confirm(
                f"Remove backups at {vault_root / '.brain' / 'backups'}?",
                default=True,
            )
        else:
            # Vault is going away — backups go with it automatically.
            remove_backups = False

    outcome = _Outcome()

    # --- Step a: Claude Desktop MCP entry -----------------------------------
    if yes:
        # Non-interactive: always remove if present.
        if _mcp_is_installed():
            _remove_mcp(outcome)
    elif do_remove_mcp:
        _remove_mcp(outcome)

    # --- Step b: backups ----------------------------------------------------
    if vault_preserved and remove_backups:
        _remove_backups(vault_root, outcome)

    # --- Step c: code install dir ------------------------------------------
    _remove_code(install_dir, outcome)

    # --- Step d: shims + .app wrapper --------------------------------------
    _remove_shims(outcome)
    _remove_app_wrapper(outcome)

    # --- Step e: vault (only if user opted in) -----------------------------
    if not vault_preserved:
        _remove_vault(vault_root, outcome)

    _print_summary(outcome, vault_root=vault_root, vault_preserved=vault_preserved)
