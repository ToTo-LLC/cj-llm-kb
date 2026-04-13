"""Secrets file handling. File-based only; never round-tripped via config.json."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class SecretNotFoundError(KeyError):
    """Raised when a requested secret is not present."""


class SecretsStore:
    """Minimal .env-style key/value store at a fixed path.

    Supports `KEY=VALUE` lines (values may contain `=`), blank lines, and `#` comments.
    On POSIX, writes are chmod 600. On Windows, ACL restriction is handled by caller
    or by the default user profile permissions.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            self._data[key.strip()] = value

    def get(self, key: str) -> str:
        try:
            return self._data[key]
        except KeyError as exc:
            raise SecretNotFoundError(key) from exc

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}" for k, v in sorted(self._data.items())]
        self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if sys.platform != "win32":
            os.chmod(self._path, 0o600)

    def has(self, key: str) -> bool:
        return key in self._data
