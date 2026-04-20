"""brain_api auth primitives — token generation, filesystem IO.

Task 7 lands the token-file primitives. Task 8 adds Origin/Host middleware;
Task 9 adds the FastAPI dependency that enforces X-Brain-Token on write routes.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import sys
from pathlib import Path

_TOKEN_FILENAME = "api-secret.txt"


def generate_token() -> str:
    """Return a fresh 32-byte (256-bit) hex token. Rotation-safe."""
    return secrets.token_hex(32)


def _token_path(vault_root: Path) -> Path:
    return vault_root / ".brain" / "run" / _TOKEN_FILENAME


def write_token_file(vault_root: Path, token: str) -> Path:
    """Write ``token`` to ``<vault>/.brain/run/api-secret.txt`` with mode 0600.

    POSIX: atomic-ish via ``os.open(..., O_CREAT | O_WRONLY | O_TRUNC, 0o600)``
    so the file is created with 0o600 before any bytes are written. A trailing
    ``os.chmod(path, 0o600)`` forces the mode even when the file already
    existed (O_CREAT without O_EXCL leaves pre-existing permissions intact).

    Windows: fall back to ``pathlib.Path.write_text`` + best-effort
    ``os.chmod(..., 0o600)``. Windows ``chmod`` only toggles the read-only
    bit — the real defense is NTFS ACLs via ``pywin32``, which Plan 05
    deliberately does NOT introduce as a new dep. See
    ``docs/testing/cross-platform.md`` for the threat-model discussion.
    """
    path = _token_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        # Windows: plain write + best-effort chmod.
        path.write_text(token + "\n", encoding="utf-8", newline="\n")
        # TODO(Windows ACL): pywin32 SetFileSecurityA for real lockdown.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    else:
        # POSIX: atomic create-with-mode. O_CREAT | O_TRUNC wipes any prior
        # contents; the mode argument applies only when the file is freshly
        # created, so we follow up with an explicit chmod for the overwrite
        # case.
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        fd = os.open(str(path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(token + "\n")
        os.chmod(path, 0o600)

    return path


def read_token_file(vault_root: Path) -> str | None:
    """Return the token from ``<vault>/.brain/run/api-secret.txt``, or None if missing."""
    path = _token_path(vault_root)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()
