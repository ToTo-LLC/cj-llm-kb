"""VCR config for brain_api chat contract tests.

Mirrors the Plan 02/04 pattern (see
`packages/brain_core/tests/prompts/conftest.py` and
`packages/brain_mcp/tests/prompts/conftest.py`). Tests marked
`@pytest.mark.vcr` are skipped unless a cassette YAML exists on disk
AND/OR `RUN_LIVE_LLM_TESTS=1` is set for recording.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

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
