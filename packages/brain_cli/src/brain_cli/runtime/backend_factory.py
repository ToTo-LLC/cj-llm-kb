"""Zero-arg factory the supervisor hands to ``uvicorn --factory``.

brain_api's ``create_app`` requires ``vault_root`` + ``allowed_domains``
arguments, which uvicorn's factory invocation cannot supply. This shim
reads them from the env vars the supervisor sets before ``Popen``:

* ``BRAIN_VAULT_ROOT``      — absolute path to the vault (required).
* ``BRAIN_ALLOWED_DOMAINS`` — comma-separated list (default: ``research,work``).

Kept in ``brain_cli.runtime`` rather than ``brain_api`` so brain_cli is
the single source of truth for "how the supervisor spawns uvicorn" — a
future swap (e.g. gunicorn) only touches this package.
"""

from __future__ import annotations

import os
from pathlib import Path

from brain_api import create_app


def build_app():  # type: ignore[no-untyped-def]
    """Build the FastAPI app for supervisor-spawned uvicorn runs.

    Raises ``RuntimeError`` if ``BRAIN_VAULT_ROOT`` is unset — the
    supervisor always sets it, so an unset value indicates the user
    invoked uvicorn directly without going through ``brain start``.
    """
    vault_root = os.environ.get("BRAIN_VAULT_ROOT")
    if not vault_root:
        raise RuntimeError(
            "BRAIN_VAULT_ROOT must be set before launching brain_api. "
            "Run via `brain start` (or set the env var manually if you "
            "know what you are doing)."
        )
    allowed = tuple(
        d.strip()
        for d in os.environ.get("BRAIN_ALLOWED_DOMAINS", "research,work").split(",")
        if d.strip()
    )
    return create_app(vault_root=Path(vault_root), allowed_domains=allowed)
