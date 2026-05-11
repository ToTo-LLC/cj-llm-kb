"""Drift gate: AutonomyCategoryFlags field set must match autonomy-categories.json fixture."""

import json
from pathlib import Path


FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "brain_web"
    / "tests"
    / "fixtures"
    / "autonomy-categories.json"
)


def test_autonomy_category_flags_matches_fixture() -> None:
    """AutonomyCategoryFlags.model_fields must match the committed fixture.

    If Python adds a 6th flag without updating the fixture, this test
    fails. If the fixture changes without updating Python, this test also
    fails. The fixture is the pinned sync point between Python and TS.
    """
    from brain_core.config.schema import AutonomyCategoryFlags

    expected = set(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    actual = set(AutonomyCategoryFlags.model_fields.keys())
    assert actual == expected, (
        f"AutonomyCategoryFlags fields drift detected.\n"
        f"  Python: {sorted(actual)}\n"
        f"  Fixture: {sorted(expected)}\n"
        f"Update {FIXTURE_PATH} to match."
    )
