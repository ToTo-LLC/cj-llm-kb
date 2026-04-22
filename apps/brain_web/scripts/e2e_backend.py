"""Zero-arg factory that uvicorn ``--factory`` can call for e2e runs.

``brain_api.create_app`` requires ``vault_root`` + ``allowed_domains``, which
``uvicorn --factory`` can't supply. This shim reads those from the
environment (set by ``start-backend-for-e2e.sh`` / ``.ps1``) and returns the
fully-wired FastAPI app. Same ``FakeLLMProvider`` default as the Python
tests — no real API keys, no network.
"""

from __future__ import annotations

import os
from pathlib import Path

from brain_api import create_app


def build_app():
    """Build the brain_api app for e2e, reading config from env vars.

    Required env:
        BRAIN_VAULT_ROOT — absolute path to the seeded vault.

    Optional env:
        BRAIN_ALLOWED_DOMAINS — comma-separated list (default: "research,work").
    """
    vault_root = os.environ.get("BRAIN_VAULT_ROOT")
    if not vault_root:
        raise RuntimeError(
            "BRAIN_VAULT_ROOT must be set to point at a seeded vault before "
            "launching the e2e backend."
        )
    allowed = tuple(
        d.strip()
        for d in os.environ.get("BRAIN_ALLOWED_DOMAINS", "research,work").split(",")
        if d.strip()
    )
    return create_app(vault_root=Path(vault_root), allowed_domains=allowed)
