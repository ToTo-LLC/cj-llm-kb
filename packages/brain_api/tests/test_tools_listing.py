"""GET /api/tools listing endpoint.

Plan 05 Task 3 lands the listing; Tasks 5/6 populate the registry as each
tool module auto-registers at import time. These tests pin the response
envelope shape and verify registered modules surface in the response.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def test_lists_all_registered_tools(client: TestClient) -> None:
    """After Plan 22 the registry has all 45 tools auto-registered.

    Plan 05 baseline: 18. Plan 07 Task 4 added 4
    (brain_recent_ingests, brain_create_domain, brain_rename_domain,
    brain_budget_override) → 22. Plan 07 Task 16 added
    ``brain_get_pending_patch`` for the pending-screen detail pane → 23.
    Plan 07 Task 20 added ``brain_fork_thread`` for the Fork dialog → 24.
    Plan 07 Task 25A added ten sweep tools for MCP install / settings /
    backup / domain admin (brain_mcp_install, brain_mcp_uninstall,
    brain_mcp_status, brain_mcp_selftest, brain_set_api_key,
    brain_ping_llm, brain_backup_create, brain_backup_list,
    brain_backup_restore, brain_delete_domain) → 34. Issue #18 added
    ``brain_list_threads`` for the left-nav recent-chats panel → 35.
    Issue #17 added ``brain_export_thread`` for the chat-sub-header
    export action → 36. Plan 16 Task 33 added two tools for the Settings
    Repair-config dialog (``brain_repair_config`` diagnostic +
    ``brain_repair_config_apply`` write) → 38. Plan 22 Task 5 added
    seven watched-folder tools (``brain_watch_folder``,
    ``brain_unwatch_folder``, ``brain_list_watched_folders``,
    ``brain_list_orphans``, ``brain_resync_folder``,
    ``brain_restore_orphan``, ``brain_delete_orphan``) → 45.

    The constant on this assert updates per plan closure (Plan 22 T17
    cleared the pre-existing 38-vs-actual drift; see
    `tasks/lessons.md` Plan 22 section).
    """
    response = client.get("/api/tools")
    body = response.json()
    names = {t["name"] for t in body["tools"]}
    assert len(body["tools"]) == 45
    # Spot-check a few names across all groups.
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
    # Plan 07 Task 25A additions — the 10 sweep tools.
    assert "brain_mcp_install" in names
    assert "brain_mcp_uninstall" in names
    assert "brain_mcp_status" in names
    assert "brain_mcp_selftest" in names
    assert "brain_set_api_key" in names
    assert "brain_ping_llm" in names
    assert "brain_backup_create" in names
    assert "brain_backup_list" in names
    assert "brain_backup_restore" in names
    assert "brain_delete_domain" in names
    # Issue #18 — left-nav recent-chats data source.
    assert "brain_list_threads" in names
    # Issue #17 — chat-sub-header export-thread action.
    assert "brain_export_thread" in names
    # Plan 16 Task 33 — Settings Repair-config dialog.
    assert "brain_repair_config" in names
    assert "brain_repair_config_apply" in names
    # Plan 22 Task 5 — watched-folders subsystem (7 tools).
    assert "brain_watch_folder" in names
    assert "brain_unwatch_folder" in names
    assert "brain_list_watched_folders" in names
    assert "brain_list_orphans" in names
    assert "brain_resync_folder" in names
    assert "brain_restore_orphan" in names
    assert "brain_delete_orphan" in names


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
