"""Smoke test for brain_core.tools.recent_ingests — ToolResult shape."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from brain_core.state.db import StateDB
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.recent_ingests import NAME, handle


def _mk_ctx(vault: Path, *, db: StateDB | None = None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=db,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_recent_ingests"


async def test_empty_when_no_state_db(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data == {"ingests": []}


async def test_returns_inserted_rows_newest_first(tmp_path: Path) -> None:
    db_path = tmp_path / ".brain" / "state.sqlite"
    db = StateDB.open(db_path)
    try:
        # Insert two rows; newest should sort first.
        old_ts = datetime(2026, 4, 10, tzinfo=UTC).isoformat()
        new_ts = datetime(2026, 4, 15, tzinfo=UTC).isoformat()
        for source, status, ts in [
            ("https://old.example.com", "ok", old_ts),
            ("https://new.example.com", "quarantined", new_ts),
        ]:
            db.exec(
                "INSERT INTO ingest_history "
                "(source, source_type, domain, status, patch_id, classified_at, cost_usd, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source, "url", "research", status, None, ts, 0.0, None),
            )

        result = await handle({"limit": 5}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()

    assert isinstance(result, ToolResult)
    assert result.data is not None
    ingests = result.data["ingests"]
    assert len(ingests) == 2
    assert ingests[0]["source"] == "https://new.example.com"
    assert ingests[0]["status"] == "quarantined"
    assert ingests[1]["source"] == "https://old.example.com"
    assert ingests[1]["status"] == "ok"
