"""brain_core.state — shared SQLite primitives. Vault is source of truth; state is cache."""

from brain_core.state.db import StateDB

__all__ = ["StateDB"]
