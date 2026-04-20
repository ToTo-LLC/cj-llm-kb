"""Tests for brain_api.auth — token generation + filesystem IO."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from brain_api.auth import generate_token, read_token_file, write_token_file


def test_generate_token_is_64_hex_chars() -> None:
    tok = generate_token()
    assert isinstance(tok, str)
    assert len(tok) == 64
    assert all(c in "0123456789abcdef" for c in tok)


def test_generate_token_is_unique() -> None:
    # Collision probability is ~2^-256 — one thousand samples are safely distinct.
    tokens = {generate_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_write_token_file_creates_parent_and_writes(tmp_path: Path) -> None:
    token = generate_token()
    path = write_token_file(tmp_path, token)

    assert path == tmp_path / ".brain" / "run" / "api-secret.txt"
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip() == token


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_write_token_file_is_mode_0600_on_posix(tmp_path: Path) -> None:
    token = generate_token()
    path = write_token_file(tmp_path, token)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_write_token_file_overwrites_prior(tmp_path: Path) -> None:
    path = write_token_file(tmp_path, "aaaa")
    path2 = write_token_file(tmp_path, "bbbb")
    assert path == path2
    assert path.read_text(encoding="utf-8").strip() == "bbbb"


def test_read_token_file_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_token_file(tmp_path) is None


def test_read_token_file_returns_written_token(tmp_path: Path) -> None:
    token = generate_token()
    write_token_file(tmp_path, token)
    assert read_token_file(tmp_path) == token


def test_lifespan_generates_and_stashes_token(app, seeded_vault: Path) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app):
        ctx = app.state.ctx
        assert ctx.token is not None
        assert len(ctx.token) == 64
        # File on disk matches.
        on_disk = read_token_file(seeded_vault)
        assert on_disk == ctx.token


def test_each_create_app_rotates_token(seeded_vault: Path) -> None:
    """Rotation on startup — a second create_app invocation writes a new token."""
    from brain_api import create_app
    from fastapi.testclient import TestClient

    app_a = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app_a):
        tok_a = app_a.state.ctx.token

    app_b = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app_b):
        tok_b = app_b.state.ctx.token

    assert tok_a != tok_b
