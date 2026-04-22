"""``brain upgrade`` — Plan 08 Task 5.

Flow:

1. Read current version (from ``<install>/VERSION`` or ``brain_core.__version__``).
2. Check GitHub for a newer release (opt-out via ``BRAIN_NO_UPDATE_CHECK=1``;
   skipped entirely when ``--tarball`` is passed).
3. Show release notes, ask for confirmation (unless ``--yes``).
4. Download (or use the supplied ``--tarball``) into ``<vault>/.brain/cache/``.
5. Stop any running daemon.
6. Extract to ``<install>-staging/``.
7. ``uv sync --project <staging>`` to install Python deps.
8. Build the UI in staging via pnpm. (Node discovery is Task 7/8's job —
   for now we expect ``node`` + ``pnpm`` on PATH and error out clearly
   with a fix-hint otherwise.)
9. Run pending SQL migrations against ``<vault>/.brain/state.sqlite``.
10. Atomic swap: rename current install → ``<install>-prev-<ts>/``,
    rename staging → install.
11. Write ``<install>/VERSION``. Rotate old backups (keep last N).
12. Print a "run ``brain start``" hint.

Every step that mutates disk has a rollback path. Any failure past
step 6 rolls the staging tree back to nothing (delete partial) or
swaps the previous install back in place.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from pathlib import Path

import typer

from brain_cli.runtime import paths, pidfile, release, supervisor
from brain_cli.runtime.migrator import MigrationError, run_migrations
from brain_cli.runtime.release import ReleaseError, ReleaseInfo
from brain_cli.runtime.swap import (
    SwapError,
    stage_upgrade,
    swap_in,
)

# How many ``<install>-prev-<ts>`` backup dirs to keep after a successful
# upgrade. Configurable via env so power users can expand; default 3 is
# enough for two rollbacks without dominating disk.
_DEFAULT_KEEP_BACKUPS = 3

# Release notes shown to the user are long by default; truncate to keep
# the terminal usable. 20 lines is roughly a screenful on most boxes.
_RELEASE_NOTES_MAX_LINES = 20


def _read_current_version(install_dir: Path) -> str:
    """Version string for the installed brain.

    Priority: ``<install>/VERSION`` file → ``brain_core.__version__``.
    The install script writes the VERSION file on install so upgrades
    across a Python-patch bump (where ``brain_core.__version__`` didn't
    change) still detect correctly.
    """
    version_file = install_dir / "VERSION"
    if version_file.exists():
        try:
            raw = version_file.read_text(encoding="utf-8").strip()
            if raw:
                return raw.lstrip("v")
        except OSError:
            pass
    try:
        from brain_core import __version__ as core_version

        return core_version
    except ImportError:
        return "0.0.0"


def _render_release_notes(body: str, *, max_lines: int = _RELEASE_NOTES_MAX_LINES) -> str:
    """Clip release notes to ``max_lines``, trailing with an ellipsis if truncated."""
    lines = body.splitlines()
    if len(lines) <= max_lines:
        return body
    clipped = "\n".join(lines[:max_lines])
    return f"{clipped}\n…(truncated; full notes at the release page)"


def _stop_running_daemon(vault_root: Path) -> None:
    """Best-effort ``brain stop`` before we mess with the install dir.

    If anything goes wrong (no pid file, stale pid, psutil says process
    is gone) we silently continue — the swap step will fail loudly
    anyway if there's a real lock problem.
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


def _run_uv_sync(staging_dir: Path) -> None:
    """``uv sync --project <staging>`` — installs Python deps in staging.

    No ``--dev``: we install production deps only, same as the install
    script. Errors surface as a :class:`SwapError` so the caller's
    try/except logic has one type to catch.
    """
    cmd = ["uv", "sync", "--project", str(staging_dir), "--no-dev"]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SwapError(
            "`uv` not found on PATH. Install uv first (https://astral.sh/uv) "
            "and re-run `brain upgrade`."
        ) from exc
    if result.returncode != 0:
        raise SwapError(
            f"`uv sync` failed in staging dir: {result.stderr.strip() or result.stdout.strip()}"
        )


def _build_ui(staging_dir: Path) -> None:
    """Build Next.js static export inside the staged dir.

    Delegates to ``pnpm -F brain_web install && pnpm -F brain_web build``.
    Tasks 7/8 will add a bundled-fnm wrapper so node doesn't need to be
    on global PATH; for Task 5 we require it on PATH and error out
    clearly otherwise. This is fine because upgrade-via-tarball is
    (currently) tested only on the developer's machine.
    """
    if shutil.which("pnpm") is None:
        raise SwapError(
            "`pnpm` not found on PATH. Upgrade requires Node 20 + pnpm to "
            "rebuild the UI bundle. Install Node (https://nodejs.org) + "
            "`corepack enable`, then re-run `brain upgrade`."
        )

    for args in (
        ["pnpm", "-F", "brain_web", "install"],
        ["pnpm", "-F", "brain_web", "build"],
    ):
        try:
            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                cwd=str(staging_dir),
            )
        except FileNotFoundError as exc:
            raise SwapError(f"`{args[0]}` not found while building UI.") from exc
        if result.returncode != 0:
            raise SwapError(
                f"`{' '.join(args)}` failed: {result.stderr.strip() or result.stdout.strip()}"
            )


def _rotate_backups(install_dir: Path, keep: int) -> None:
    """Keep the ``keep`` most-recent ``<install>-prev-*`` dirs, delete the rest.

    Sort by name descending (timestamps sort lexicographically since we
    format with %Y%m%dT%H%M%SZ). Silent on deletion errors — old
    backups lingering isn't a correctness issue, just a disk-space one.
    """
    if keep < 0:
        return
    parent = install_dir.parent
    prefix = f"{install_dir.name}-prev-"
    backups = sorted(
        (p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix)),
        key=lambda p: p.name,
        reverse=True,
    )
    for stale in backups[keep:]:
        with contextlib.suppress(OSError):
            shutil.rmtree(stale)


def _write_version_file(install_dir: Path, version: str) -> None:
    """Record the new version so the next upgrade check can compare.

    Non-fatal on OSError — the next upgrade will fall back to
    ``brain_core.__version__``.
    """
    with contextlib.suppress(OSError):
        (install_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")


def upgrade(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts (for scripts / CI).",
    ),
    tarball: Path | None = typer.Option(  # noqa: B008
        None,
        "--tarball",
        help=(
            "Use a local tarball instead of downloading from GitHub "
            "(for airgap + testing). Skips the version check."
        ),
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
    keep_backups: int = typer.Option(
        int(os.environ.get("BRAIN_UPGRADE_KEEP_BACKUPS", str(_DEFAULT_KEEP_BACKUPS))),
        "--keep-backups",
        help="Number of previous-install backups to keep. Default 3.",
    ),
) -> None:
    """Upgrade brain to the latest release (or a local tarball)."""
    install_dir = install or paths.default_install_dir()
    vault_root = vault or paths.default_vault_root()
    current_version = _read_current_version(install_dir)

    # --- Step 1: find the release to install ---------------------------
    info: ReleaseInfo | None = None
    if tarball is None:
        try:
            info = release.check_latest_release(current_version=current_version)
        except ReleaseError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if info is None:
            typer.echo(f"brain is up to date (version {current_version}).")
            raise typer.Exit(code=0)

        typer.echo(f"New release available: {info.tag_name} (current: {current_version})")
        notes = _render_release_notes(info.body)
        if notes.strip():
            typer.echo("")
            typer.echo(notes)
            typer.echo("")
        if not yes:
            typer.confirm("Proceed with upgrade?", default=True, abort=True)

    # --- Step 2: materialize a tarball ---------------------------------
    cache_dir = vault_root / ".brain" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if tarball is not None:
        local_tarball = Path(tarball).expanduser().resolve()
        if not local_tarball.exists():
            typer.echo(f"error: --tarball path does not exist: {local_tarball}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"Using local tarball: {local_tarball}")
    else:
        assert info is not None  # type-narrow for mypy
        dest = cache_dir / f"brain-{info.version}.tar.gz"
        typer.echo(f"Downloading {info.tarball_url} …")
        try:
            local_tarball = release.download_release(
                info.tarball_url,
                dest,
                expected_sha256=info.sha256,
            )
        except ReleaseError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    # --- Step 3: stop the running daemon so Windows doesn't hold locks ---
    _stop_running_daemon(vault_root)

    # --- Step 4: stage ---------------------------------------------------
    try:
        staging_dir = stage_upgrade(install_dir, local_tarball)
    except SwapError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Extracted staging install to {staging_dir}")

    # --- Step 5: uv sync in staging --------------------------------------
    try:
        _run_uv_sync(staging_dir)
    except SwapError as exc:
        _cleanup_staging(staging_dir)
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # --- Step 6: build UI -------------------------------------------------
    try:
        _build_ui(staging_dir)
    except SwapError as exc:
        _cleanup_staging(staging_dir)
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # --- Step 7: migrations (against the live vault state.sqlite) -------
    state_db = vault_root / ".brain" / "state.sqlite"
    migrations_dir = _find_migrations_dir(staging_dir)
    if migrations_dir is not None:
        try:
            report = run_migrations(state_db, migrations_dir)
        except MigrationError as exc:
            _cleanup_staging(staging_dir)
            typer.echo(f"error: {exc}", err=True)
            typer.echo(
                "The state DB was left at its last successful migration; your vault is untouched.",
                err=True,
            )
            raise typer.Exit(code=1) from exc
        if report.applied:
            typer.echo(
                f"Applied {len(report.applied)} migration(s): "
                f"{report.starting_version} → {report.ending_version}"
            )

    # --- Step 8: atomic swap --------------------------------------------
    try:
        backup = swap_in(staging_dir, install_dir)
    except SwapError as exc:
        _cleanup_staging(staging_dir)
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # --- Step 9: metadata + housekeeping --------------------------------
    new_version = info.version if info is not None else _read_current_version(install_dir)
    _write_version_file(install_dir, new_version)
    _rotate_backups(install_dir, keep=keep_backups)

    typer.echo("")
    typer.echo(f"Upgraded brain to {new_version}.")
    typer.echo(f"Previous install preserved at: {backup}")
    typer.echo("Run `brain start` to launch the new version.")


def _cleanup_staging(staging_dir: Path) -> None:
    """Best-effort delete of a failed staging dir.

    Never raises — if the FS refuses, the user gets a log line and the
    next upgrade's stage_upgrade will surface a clear error about the
    lingering dir.
    """
    if not staging_dir.exists():
        return
    try:
        shutil.rmtree(staging_dir)
    except OSError as exc:
        typer.echo(
            f"warning: could not clean up staging dir {staging_dir}: {exc}. "
            "Delete it manually before retrying.",
            err=True,
        )


def _find_migrations_dir(staging_dir: Path) -> Path | None:
    """Locate the SQL migrations dir inside ``staging_dir``.

    Follows the brain_core layout:
    ``packages/brain_core/src/brain_core/state/migrations/``. Returns
    ``None`` if the dir isn't present so the caller can skip the
    migration step cleanly (e.g. a tarball with no migration files).
    """
    candidate = (
        staging_dir / "packages" / "brain_core" / "src" / "brain_core" / "state" / "migrations"
    )
    return candidate if candidate.is_dir() else None
