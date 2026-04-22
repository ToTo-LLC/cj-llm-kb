"""GET /api/tools listing endpoint.

Plan 05 Task 3 lands the listing; Tasks 5/6 populate the registry as each
tool module auto-registers at import time. These tests pin the response
envelope shape and verify registered modules surface in the response.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def test_lists_twenty_four_tools_after_plan07_task20(client: TestClient) -> None:
    """After Plan 07 Task 20, the registry has all 24 tools auto-registered.

    Plan 05 baseline: 18. Plan 07 Task 4 added 4
    (brain_recent_ingests, brain_create_domain, brain_rename_domain,
    brain_budget_override) → 22. Plan 07 Task 16 added
    ``brain_get_pending_patch`` for the pending-screen detail pane → 23.
    Plan 07 Task 20 added ``brain_fork_thread`` for the Fork dialog → 24.
    """
    response = client.get("/api/tools")
    body = response.json()
    names = {t["name"] for t in body["tools"]}
    assert len(body["tools"]) == 24
    # Spot-check a few names across all 4 groups (read/ingest/patch/maintenance).
    assert "brain_list_domains" in names
    assert "brain_ingest" in names
    assert "brain_apply_patch" in names
    assert "brain_cost_report" in names
    # Plan 07 Task 4 additions.
    assert "brain_recent_ingests" in names
    assert "brain_create_domain" in names
    assert "brain_rename_domain" in names
    assert "brain_budget_override" in names
    # Plan 07 Task 16 addition.
    assert "brain_get_pending_patch" in names
    # Plan 07 Task 20 addition.
    assert "brain_fork_thread" in names


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
