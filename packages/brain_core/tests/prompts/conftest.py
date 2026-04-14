"""Fixtures for prompts tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def prompts_fixture_dir() -> Path:
    """Return the path to the prompts test fixtures directory."""
    return Path(__file__).parent / "fixtures"


# ----------------------------------------------------------------------------
# VCR / pytest-vcr configuration for prompt contract tests.
#
# Task 20 lands this scaffolding. Task 21 (recording real cassettes) is
# deferred until an ANTHROPIC_API_KEY is available. When there are no
# cassettes on disk, tests marked `@pytest.mark.vcr` are skipped rather than
# attempting a live network call.
#
# Two-mode pattern:
#   - Normal mode: cassettes replay, no network, no key required.
#   - Record mode: `RUN_LIVE_LLM_TESTS=1` allows live requests and re-records.
# See `docs/testing/prompts-vcr.md` for details.
# ----------------------------------------------------------------------------

_CASSETTES_DIR = Path(__file__).parent / "cassettes"

_REDACTED_HEADERS: tuple[tuple[str, str], ...] = (
    ("authorization", "REDACTED"),
    ("x-api-key", "REDACTED"),
    ("anthropic-api-key", "REDACTED"),
)


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    """pytest-vcr module-level config. Consumed by pytest-vcr automatically."""
    record_mode = "new_episodes" if os.environ.get("RUN_LIVE_LLM_TESTS") == "1" else "none"
    return {
        "cassette_library_dir": str(_CASSETTES_DIR),
        "record_mode": record_mode,
        "filter_headers": list(_REDACTED_HEADERS),
        "decode_compressed_response": True,
    }


def _cassette_exists(name: str) -> bool:
    """Return True if a cassette YAML file exists for the given test name."""
    return (_CASSETTES_DIR / f"{name}.yaml").exists()
