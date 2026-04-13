"""Path normalization and scope enforcement. The domain firewall lives here."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class ScopeError(PermissionError):
    """Raised when a path is outside the allowed domain scope."""


def scope_guard(
    path: Path,
    *,
    vault_root: Path,
    allowed_domains: Iterable[str],
) -> Path:
    """Return the resolved path if it is inside an allowed domain, else raise ScopeError.

    Enforcement:
    - Resolves symlinks and `..` segments.
    - Requires the resolved path to be a descendant of vault_root.
    - Requires the first path component under vault_root to be in allowed_domains.
    """
    vault_root = vault_root.resolve()
    resolved = path.resolve()

    try:
        rel = resolved.relative_to(vault_root)
    except ValueError as exc:
        raise ScopeError(f"{path} is not inside vault {vault_root}") from exc

    if not rel.parts:
        raise ScopeError(f"{path} resolves to vault root, not a domain")

    domain = rel.parts[0]
    allowed = tuple(allowed_domains)
    if domain not in allowed:
        raise ScopeError(f"{path} domain {domain!r} not in allowed {allowed}")

    return resolved
