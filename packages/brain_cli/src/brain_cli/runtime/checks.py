"""Cross-platform health checks for ``brain doctor``.

Plan 08 Task 4. Ten read-only checks that inspect the install dir, vault,
token, config, sqlite caches, UI bundle, and runtime deps (``uv``, Node).
Each function returns a :class:`CheckResult` with a plain-English
``message`` and — on failures — an actionable ``fix_hint``.

Every check is pure: it takes its path inputs as arguments (defaulted from
env / platform defaults) and returns a dataclass. The command layer
composes them + renders the final output.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from brain_core.config.schema import Config
from pydantic import ValidationError

from brain_cli.runtime import portprobe

CheckStatus = Literal["pass", "warn", "fail", "info"]


@dataclass
class CheckResult:
    """One line of ``brain doctor`` output.

    - ``name``: short human label (e.g. ``"uv"``, ``"vault"``).
    - ``status``: one of ``pass``, ``warn``, ``fail``, ``info``.
    - ``message``: one-line status (always present — we never emit blanks).
    - ``fix_hint``: populated on ``warn``/``fail`` with a next-action
      sentence; ``None`` on ``pass``/``info``.
    """

    name: str
    status: CheckStatus
    message: str
    fix_hint: str | None = None

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable form for ``--json`` mode."""
        return asdict(self)


# --------------------------------------------------------------------------
# Path resolution helpers. Duplicated from ``commands/start.py`` on purpose
# — keeping these local to the runtime subpackage means ``checks.py`` has
# no dependency on any command module.
# --------------------------------------------------------------------------


def default_install_dir() -> Path:
    """Same priority order as ``commands.start._resolve_install_dir``."""
    env = os.environ.get("BRAIN_INSTALL_DIR")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Applications" / "brain"
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "brain"
        return Path.home() / "AppData" / "Local" / "brain"
    return Path.home() / ".local" / "share" / "brain"


def default_vault_root() -> Path:
    env = os.environ.get("BRAIN_VAULT_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "brain"


# --------------------------------------------------------------------------
# 1. uv
# --------------------------------------------------------------------------


_MIN_UV_VERSION = (0, 4, 0)


def _parse_version(text: str) -> tuple[int, ...] | None:
    """Parse ``"uv 0.8.12"`` → ``(0, 8, 12)``; returns ``None`` on garbage."""
    for token in text.split():
        parts = token.split(".")
        if len(parts) >= 2 and all(p.isdigit() for p in parts[:3]):
            return tuple(int(p) for p in parts[:3])
    return None


def check_uv() -> CheckResult:
    """Check ``uv`` is on PATH and ≥ 0.4.0."""
    try:
        proc = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError:
        return CheckResult(
            name="uv",
            status="fail",
            message="uv not found on PATH",
            fix_hint=(
                "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
            ),
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="uv",
            status="fail",
            message="uv --version hung for 5s",
            fix_hint="Reinstall uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    if proc.returncode != 0:
        return CheckResult(
            name="uv",
            status="fail",
            message=f"uv --version exited {proc.returncode}",
            fix_hint="Reinstall uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    version = _parse_version(proc.stdout)
    if version is None:
        return CheckResult(
            name="uv",
            status="warn",
            message=f"uv present but unparseable version: {proc.stdout.strip()!r}",
            fix_hint="Upgrade uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    if version < _MIN_UV_VERSION:
        return CheckResult(
            name="uv",
            status="fail",
            message=f"uv {'.'.join(str(p) for p in version)} (need ≥ 0.4.0)",
            fix_hint="Upgrade uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    return CheckResult(
        name="uv",
        status="pass",
        message=f"uv {'.'.join(str(p) for p in version)}",
    )


# --------------------------------------------------------------------------
# 2. install dir
# --------------------------------------------------------------------------


def check_install_dir(install_dir: Path | None = None) -> CheckResult:
    """Check the install directory exists and contains a ``.venv/``."""
    install = install_dir or default_install_dir()
    if not install.exists():
        return CheckResult(
            name="install_dir",
            status="fail",
            message=f"install dir missing: {install}",
            fix_hint=(
                "Reinstall: curl -LsSf https://raw.githubusercontent.com"
                "/ToTo-LLC/cj-llm-kb/main/scripts/install.sh | bash"
            ),
        )
    if not (install / ".venv").exists():
        return CheckResult(
            name="install_dir",
            status="fail",
            message=f"{install} has no .venv/",
            fix_hint=f"Run `uv sync --project {install}` to recreate the venv.",
        )
    return CheckResult(
        name="install_dir",
        status="pass",
        message=f"install dir: {install}",
    )


# --------------------------------------------------------------------------
# 3. venv
# --------------------------------------------------------------------------


def check_venv(install_dir: Path | None = None) -> CheckResult:
    """Check the venv can import ``brain_core`` cleanly.

    Runs ``<uv> run --project <install> python -c "import brain_core"`` in a
    subprocess so we exercise the *actual* venv, not the interpreter running
    ``brain doctor`` (they differ in the installed case). We resolve ``uv``
    via :func:`shutil.which` so this works even when brain_cli itself was
    launched under ``uv run`` (nested invocation) — a child process of
    ``uv run`` has the venv's ``bin/`` on PATH but not ``~/.local/bin/``
    where uv is installed, so a bare ``["uv", ...]`` Popen would fail.
    """
    install = install_dir or default_install_dir()

    if not (install / ".venv").exists():
        # Redundant with check_install_dir, but the command runs both so
        # this is a legitimate early-exit rather than duplication.
        return CheckResult(
            name="venv",
            status="fail",
            message=f"{install}/.venv missing",
            fix_hint=f"Run `uv sync --project {install}`.",
        )

    uv_path = shutil.which("uv")
    if uv_path is None:
        return CheckResult(
            name="venv",
            status="fail",
            message="uv not on PATH (needed to run the venv)",
            fix_hint="Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    try:
        proc = subprocess.run(
            [
                uv_path,
                "run",
                "--project",
                str(install),
                "python",
                "-c",
                "import brain_core; print('ok')",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except FileNotFoundError:
        return CheckResult(
            name="venv",
            status="fail",
            message="uv not on PATH (needed to run the venv)",
            fix_hint="Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="venv",
            status="fail",
            message="venv import timed out after 15s",
            fix_hint=f"Run `uv sync --project {install}`.",
        )

    if proc.returncode != 0:
        return CheckResult(
            name="venv",
            status="fail",
            message="venv can't import brain_core",
            fix_hint=f"Run `uv sync --project {install}`.",
        )

    return CheckResult(
        name="venv",
        status="pass",
        message="venv imports brain_core cleanly",
    )


# --------------------------------------------------------------------------
# 4. node (INFO only — never FAIL)
# --------------------------------------------------------------------------


def _find_bundled_node(install_dir: Path) -> Path | None:
    """Look for a node binary shipped under ``<install>/tools/fnm/``.

    We probe both the Mac/Linux layout (``installation/bin/node``) and the
    Windows layout (``installation/node.exe``) — and also glob one level
    above in case fnm lays things out slightly differently.
    """
    fnm_root = install_dir / "tools" / "fnm" / "node-versions"
    if not fnm_root.exists():
        return None

    if sys.platform == "win32":
        patterns = ["*/installation/node.exe", "*/node.exe"]
    else:
        patterns = ["*/installation/bin/node", "*/bin/node"]

    for pattern in patterns:
        for candidate in fnm_root.glob(pattern):
            if candidate.exists():
                return candidate
    return None


def check_node(install_dir: Path | None = None) -> CheckResult:
    """Report Node presence. ALWAYS INFO — Node isn't required at runtime."""
    install = install_dir or default_install_dir()

    node_path: str | None = shutil.which("node")
    bundled = _find_bundled_node(install)
    target: str | None = node_path or (str(bundled) if bundled else None)

    if target is None:
        return CheckResult(
            name="node",
            status="info",
            message="Node not found (not required at runtime; `brain upgrade` needs it).",
        )

    try:
        proc = subprocess.run(
            [target, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return CheckResult(
            name="node",
            status="info",
            message=f"Node found at {target} but ``--version`` failed (not required at runtime).",
        )

    version = proc.stdout.strip().lstrip("v") or "unknown"
    return CheckResult(
        name="node",
        status="info",
        message=f"Node {version} at {target}",
    )


# --------------------------------------------------------------------------
# 5. ports
# --------------------------------------------------------------------------


def check_ports(start: int = 4317, end: int = 4330) -> CheckResult:
    """Report how many of the 4317..4330 range are free."""
    total = end - start + 1
    free = sum(1 for port in range(start, end + 1) if portprobe.is_port_free(port))
    message = f"ports {start}-{end}: {free}/{total} free"
    if free == 0:
        return CheckResult(
            name="ports",
            status="fail",
            message=f"ports {start}-{end}: 0/{total} free",
            fix_hint=(
                "Every port in the brain range is bound. Check for another "
                "brain instance or stray local servers."
            ),
        )
    if free < 3:
        return CheckResult(
            name="ports",
            status="warn",
            message=message,
            fix_hint="Fewer than 3 free ports in the brain range — you may hit "
            "conflicts at `brain start`.",
        )
    return CheckResult(name="ports", status="pass", message=message)


# --------------------------------------------------------------------------
# 6. vault
# --------------------------------------------------------------------------


def check_vault(vault_root: Path | None = None) -> CheckResult:
    """Vault dir exists + is writable (via a real write probe)."""
    vault = vault_root or default_vault_root()
    if not vault.exists():
        return CheckResult(
            name="vault",
            status="fail",
            message=f"vault missing: {vault}",
            fix_hint=f"Create vault: mkdir -p '{vault}'",
        )
    if not vault.is_dir():
        return CheckResult(
            name="vault",
            status="fail",
            message=f"vault path is not a directory: {vault}",
            fix_hint=f"Remove the file and create the vault dir: mkdir -p '{vault}'",
        )
    if not os.access(vault, os.W_OK):
        return CheckResult(
            name="vault",
            status="fail",
            message=f"vault not writable: {vault}",
            fix_hint=f"Fix permissions: chmod u+w '{vault}'",
        )

    # Real write probe (catches read-only filesystems + ACL traps).
    probe_dir = vault / ".brain" / "tmp"
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe = probe_dir / "doctor-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            name="vault",
            status="fail",
            message=f"vault write probe failed: {exc}",
            fix_hint=f"Check disk space + permissions on '{vault}'.",
        )

    return CheckResult(
        name="vault",
        status="pass",
        message=f"vault writable: {vault}",
    )


# --------------------------------------------------------------------------
# 7. token
# --------------------------------------------------------------------------


def check_token(vault_root: Path | None = None) -> CheckResult:
    """Check the API token file exists + has tight perms on Unix."""
    vault = vault_root or default_vault_root()
    token = vault / ".brain" / "run" / "api-secret.txt"

    if not token.exists():
        return CheckResult(
            name="token",
            status="fail",
            message=f"token file missing at {token}",
            fix_hint="Run `brain setup` to regenerate the token.",
        )

    size = token.stat().st_size

    if sys.platform != "win32":
        mode = token.stat().st_mode & 0o777
        if mode != 0o600:
            return CheckResult(
                name="token",
                status="warn",
                message=f"token file mode is 0o{mode:o} (expected 0600)",
                fix_hint=f"Tighten perms: chmod 600 '{token}'",
            )
        return CheckResult(
            name="token",
            status="pass",
            message=f"token file: 0600, {size} bytes",
        )

    # Windows: ACL-based; no mode check.
    return CheckResult(
        name="token",
        status="pass",
        message=f"token file: {size} bytes",
    )


# --------------------------------------------------------------------------
# 8. config
# --------------------------------------------------------------------------


def check_config(vault_root: Path | None = None) -> CheckResult:
    """Parse + validate ``<vault>/.brain/config.json`` against the schema."""
    vault = vault_root or default_vault_root()
    cfg = vault / ".brain" / "config.json"

    if not cfg.exists():
        return CheckResult(
            name="config",
            status="warn",
            message=f"config.json missing at {cfg} (defaults will be used)",
            fix_hint="Run `brain setup` to write a config, or let defaults apply.",
        )

    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(
            name="config",
            status="fail",
            message=f"config.json is not valid JSON: {exc}",
            fix_hint="Fix the config file or reset it: `brain config reset`",
        )

    try:
        parsed = Config(**data)
    except (ValidationError, TypeError) as exc:
        return CheckResult(
            name="config",
            status="fail",
            message=f"config.json fails schema validation: {type(exc).__name__}",
            fix_hint="Fix the invalid keys or reset: `brain config reset`",
        )

    return CheckResult(
        name="config",
        status="pass",
        message=f"config valid, active_domain={parsed.active_domain}",
    )


# --------------------------------------------------------------------------
# 9. sqlite
# --------------------------------------------------------------------------


_SQLITE_DBS = ("state.sqlite", "costs.sqlite")


def check_sqlite(vault_root: Path | None = None) -> CheckResult:
    """Open each sqlite cache and run ``PRAGMA integrity_check``.

    We tolerate a db that doesn't exist yet — fresh installs haven't run
    a single ingest. Only *corrupt* existing files flip the check to FAIL.
    """
    vault = vault_root or default_vault_root()
    brain = vault / ".brain"

    reports: list[str] = []
    failures: list[str] = []

    for name in _SQLITE_DBS:
        path = brain / name
        if not path.exists():
            reports.append(f"{name}: absent (ok — will be created on first use)")
            continue
        try:
            conn = sqlite3.connect(path)
            try:
                row = conn.execute("PRAGMA integrity_check").fetchone()
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            failures.append(f"{name}: {exc}")
            continue
        if not row or row[0] != "ok":
            failures.append(f"{name}: integrity_check returned {row!r}")
            continue
        size_kb = max(1, path.stat().st_size // 1024)
        reports.append(f"{name}: {size_kb}KB")

    if failures:
        return CheckResult(
            name="sqlite",
            status="fail",
            message="; ".join(failures),
            fix_hint=(
                "Rebuild the cache: `brain doctor --rebuild-cache` "
                "(restore from `.brain/backups/` if needed)."
            ),
        )

    return CheckResult(
        name="sqlite",
        status="pass",
        message="; ".join(reports),
    )


# --------------------------------------------------------------------------
# 10. UI bundle
# --------------------------------------------------------------------------


def check_ui_bundle(install_dir: Path | None = None) -> CheckResult:
    """Ensure the Next.js static-export bundle is present.

    We accept either the packaged layout (``<install>/web/out/``) or the
    dev/repo layout (``<install>/apps/brain_web/out/``) — matches the
    resolution order in ``commands.start._resolve_web_out_dir``.
    """
    install = install_dir or default_install_dir()
    candidates = [
        install / "web" / "out" / "index.html",
        install / "apps" / "brain_web" / "out" / "index.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return CheckResult(
                name="ui_bundle",
                status="pass",
                message=f"UI bundle: {candidate.parent}",
            )
    return CheckResult(
        name="ui_bundle",
        status="fail",
        message=f"no UI bundle under {install}",
        fix_hint=(
            "Rebuild UI: `pnpm -F brain_web build` in the install dir, or run "
            "`brain upgrade`."
        ),
    )
