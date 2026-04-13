"""Append-only per-domain log.md. Entry format: ## [YYYY-MM-DD HH:MM] op | summary"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HEADING = re.compile(r"^##\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(\S+)\s*\|\s*(.*)$")


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    op: str
    summary: str

    def render(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"## [{ts}] {self.op} | {self.summary}"


class LogFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.exists():
            path.write_text(f"# {path.parent.name} — log\n", encoding="utf-8")

    def append(self, entry: LogEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write("\n" + entry.render() + "\n")

    def read_all(self) -> list[LogEntry]:
        out: list[LogEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            m = _HEADING.match(line)
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                out.append(LogEntry(timestamp=ts, op=m.group(2), summary=m.group(3)))
        return out

    def read_last(self, n: int) -> list[LogEntry]:
        return self.read_all()[-n:]
