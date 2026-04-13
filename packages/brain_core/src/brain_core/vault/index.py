"""index.md parser/writer. Four-section layout: Sources, Entities, Concepts, Synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS: tuple[str, ...] = ("Sources", "Entities", "Concepts", "Synthesis")
_ENTRY_RE = re.compile(r"^- \[\[([^\]]+)\]\]\s*—\s*(.*)$")


@dataclass(frozen=True)
class IndexEntry:
    target: str
    summary: str

    def render(self) -> str:
        return f"- [[{self.target}]] — {self.summary}"


@dataclass
class IndexFile:
    path: Path
    title: str
    sections: dict[str, list[IndexEntry]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "IndexFile":
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else path.stem
        sections: dict[str, list[IndexEntry]] = {s: [] for s in SECTIONS}
        current: str | None = None
        for line in lines[1:]:
            if line.startswith("## "):
                current = line[3:].strip()
                sections.setdefault(current, [])
                continue
            if current is None:
                continue
            m = _ENTRY_RE.match(line.rstrip())
            if m:
                sections[current].append(IndexEntry(target=m.group(1), summary=m.group(2)))
        return cls(path=path, title=title, sections=sections)

    def add_entry(self, section: str, entry: IndexEntry) -> None:
        self.sections.setdefault(section, []).append(entry)

    def remove_entry(self, section: str, *, target: str) -> None:
        self.sections[section] = [e for e in self.sections.get(section, []) if e.target != target]

    def render(self) -> str:
        parts = [f"# {self.title}", ""]
        for section in SECTIONS:
            parts.append(f"## {section}")
            entries = self.sections.get(section, [])
            for e in entries:
                parts.append(e.render())
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def save(self) -> None:
        self.path.write_text(self.render(), encoding="utf-8")
