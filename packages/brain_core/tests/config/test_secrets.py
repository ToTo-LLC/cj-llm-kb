from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from brain_core.config.secrets import SecretNotFoundError, SecretsStore


def test_read_existing_secret(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("ANTHROPIC_API_KEY=sk-test-123\n", encoding="utf-8")
    store = SecretsStore(f)
    assert store.get("ANTHROPIC_API_KEY") == "sk-test-123"


def test_missing_secret_raises(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("", encoding="utf-8")
    with pytest.raises(SecretNotFoundError):
        SecretsStore(f).get("NOPE")


def test_set_and_persist(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    store = SecretsStore(f)
    store.set("ANTHROPIC_API_KEY", "sk-abc")
    assert f.exists()
    assert SecretsStore(f).get("ANTHROPIC_API_KEY") == "sk-abc"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only permission check")
def test_set_creates_mode_600(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    SecretsStore(f).set("K", "V")
    mode = stat.S_IMODE(os.stat(f).st_mode)
    assert mode == 0o600


def test_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("# comment\n\nA=1\nB=2\n# B=99\n", encoding="utf-8")
    store = SecretsStore(f)
    assert store.get("A") == "1"
    assert store.get("B") == "2"


def test_values_with_equals_sign(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("TOKEN=abc=def=ghi\n", encoding="utf-8")
    assert SecretsStore(f).get("TOKEN") == "abc=def=ghi"


def test_has_returns_membership(tmp_path: Path) -> None:
    f = tmp_path / "secrets.env"
    f.write_text("A=1\n", encoding="utf-8")
    store = SecretsStore(f)
    assert store.has("A") is True
    assert store.has("MISSING") is False
