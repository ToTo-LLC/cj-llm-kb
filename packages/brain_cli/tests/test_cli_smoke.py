"""Smoke test — CLI entry point wires Typer root."""

from __future__ import annotations

from brain_cli.app import app
from typer.testing import CliRunner


def test_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "brain" in result.stdout.lower()
    assert "0.1.0" in result.stdout


def test_help_shows_app_name() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "brain" in result.stdout.lower()
