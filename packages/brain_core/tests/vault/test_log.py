from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from brain_core.vault.log import LogEntry, LogFile


def test_append_and_parse(ephemeral_vault: Path) -> None:
    log_path = ephemeral_vault / "research" / "log.md"
    lf = LogFile(log_path)
    ts = datetime(2026, 4, 13, 14, 22, tzinfo=UTC)
    lf.append(
        LogEntry(
            timestamp=ts, op="ingest", summary="source | [[alpha]] | touched: index, concepts/x"
        )
    )
    lf.append(LogEntry(timestamp=ts, op="query", summary='"what is x" | used: alpha'))

    entries = LogFile(log_path).read_all()
    assert len(entries) == 2
    assert entries[0].op == "ingest"
    assert "alpha" in entries[0].summary
    assert entries[1].op == "query"


def test_read_last_n(ephemeral_vault: Path) -> None:
    log_path = ephemeral_vault / "research" / "log.md"
    lf = LogFile(log_path)
    for i in range(10):
        lf.append(
            LogEntry(timestamp=datetime(2026, 4, 13, tzinfo=UTC), op="ingest", summary=f"n{i}")
        )
    tail = LogFile(log_path).read_last(3)
    assert [e.summary for e in tail] == ["n7", "n8", "n9"]
