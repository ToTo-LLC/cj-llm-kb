"""Fixtures for prompts tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def prompts_fixture_dir() -> Path:
    """Return the path to the prompts test fixtures directory."""
    return Path(__file__).parent / "fixtures"
