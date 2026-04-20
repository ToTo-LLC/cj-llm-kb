"""GET /api/tools listing endpoint.

Plan 05 Task 3 lands the listing. Until Tasks 5/6 populate the registry, the
endpoint returns an empty list; these tests pin the baseline shape and verify
registered modules surface in the response.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def test_empty_registry_returns_empty_list(client: TestClient) -> None:
    """Baseline: with no tools registered, GET /api/tools returns an empty list."""
    response = client.get("/api/tools")
    assert response.status_code == 200
    assert response.json() == {"tools": []}


def test_listing_shape_matches_schema(client: TestClient) -> None:
    """Response envelope is {"tools": [...]}, independent of population."""
    response = client.get("/api/tools")
    assert response.status_code == 200
    body = response.json()
    assert "tools" in body
    assert isinstance(body["tools"], list)


def test_listing_reflects_registered_tools(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A monkeypatched fake module appears in the response in sorted order."""
    from brain_core import tools as tools_registry

    fake = SimpleNamespace(
        NAME="fake_tool",
        DESCRIPTION="for testing",
        INPUT_SCHEMA={"type": "object", "properties": {}},
    )
    monkeypatch.setattr(tools_registry, "_TOOL_MODULES", [fake])
    response = client.get("/api/tools")
    assert response.status_code == 200
    assert response.json() == {
        "tools": [
            {
                "name": "fake_tool",
                "description": "for testing",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
    }
