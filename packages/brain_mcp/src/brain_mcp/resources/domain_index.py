"""brain://<domain>/index.md resource — one URI per allowed domain.

URI shape: `brain://research/index.md`. We use `urllib.parse.urlparse` rather
than string splitting so that (a) `brain://` with no netloc fails explicitly
and (b) a trailing path of anything other than `/index.md` is rejected rather
than silently read as the domain index.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from brain_core.vault.paths import ScopeError, scope_guard

MIME_TYPE = "text/markdown"


def uri_for(domain: str) -> str:
    """Build the resource URI for a domain's index.md."""
    return f"brain://{domain}/index.md"


def parse_domain(uri: str) -> str:
    """Extract the `<domain>` segment from `brain://<domain>/index.md`.

    Raises ValueError on any other shape. Scope enforcement is a separate step
    in `read()` — this function only parses.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "brain":
        raise ValueError(f"not a brain:// URI: {uri!r}")
    domain = parsed.netloc
    if not domain or parsed.path != "/index.md":
        raise ValueError(f"not a domain index URI: {uri!r}")
    return domain


def read(uri: str, *, vault_root: Path, allowed_domains: tuple[str, ...]) -> str:
    """Return the domain index body.

    Raises ScopeError if the URI's domain is not in `allowed_domains`. Returns
    an empty string if the index file doesn't exist yet (valid pre-ingest state).
    """
    domain = parse_domain(uri)
    if domain not in allowed_domains:
        raise ScopeError(f"domain {domain!r} not in allowed {allowed_domains}")
    idx = scope_guard(
        vault_root / domain / "index.md",
        vault_root=vault_root,
        allowed_domains=allowed_domains,
    )
    if not idx.exists():
        return ""
    return idx.read_text(encoding="utf-8")
