"""brain://config/public — non-secret subset of the current configuration.

ALLOWLIST, not denylist. Only fields named in `_PUBLIC_FIELDS` ever leave the
server; anything else in the Config model (current or future) is dropped by
default. This is the safety model: adding a new secret field to `Config`
cannot leak it accidentally — it just won't appear in the public view until
someone explicitly adds its name to `_PUBLIC_FIELDS`.

We build the public dict from `vault_root` + spec defaults rather than calling
`brain_core.config.loader.load_config(...)` because `load_config` requires an
env Mapping + cli_overrides args that the MCP server doesn't have access to,
and the vault in-session may not have a `.brain/config.json` file at all. The
served values reflect the session's *resolved* settings, which is what a
client actually wants to see.
"""

from __future__ import annotations

import json
from pathlib import Path

from brain_core.config.schema import BudgetConfig, Config

URI = "brain://config/public"
NAME = "config/public"
DESCRIPTION = "Non-secret subset of the brain configuration (vault root, active domain, budget)."
MIME_TYPE = "application/json"

# Any field not in this allowlist is omitted from the public payload.
# Keep this list in sync with spec §7 when public config expands.
_PUBLIC_FIELDS: frozenset[str] = frozenset(
    {
        "vault_root",
        "active_domain",
        "budget",
        "log_llm_payloads",
    }
)


def read(vault_root: Path, *, active_domain: str = "research") -> str:
    """Return a JSON string of the public config subset.

    Only keys in `_PUBLIC_FIELDS` are included. The output is pretty-printed
    JSON for easy inspection in Claude Desktop's resource pane.
    """
    # Build a Config from defaults to pull per-field defaults (e.g. budget).
    defaults = Config()
    budget: BudgetConfig = defaults.budget
    source: dict[str, object] = {
        "vault_root": str(vault_root),
        "active_domain": active_domain,
        "budget": budget.model_dump(mode="json"),
        "log_llm_payloads": defaults.log_llm_payloads,
    }
    public = {k: v for k, v in source.items() if k in _PUBLIC_FIELDS}
    return json.dumps(public, indent=2, default=str)
