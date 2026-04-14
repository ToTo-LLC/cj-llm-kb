"""Chat-thread Markdown writer/reader. All writes flow through VaultWriter.

Thread files live at <domains[0]>/chats/<thread_id>.md. Per turn, the file
is fully rewritten via VaultWriter.apply - first as a NewFile patch, then as
Edit patches with old=full_body, new=full_body. VaultWriter's atomicity +
undo log apply per write.

Also upserts chat_threads metadata in state.sqlite after every write so that
the list_chats tool (Task 9) sees recent activity.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.state.db import StateDB
from brain_core.vault.frontmatter import parse_frontmatter
from brain_core.vault.types import Edit, NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


@dataclass(frozen=True)
class LoadedThread:
    config: ChatSessionConfig
    turns: list[ChatTurn]


_SECTION_RE = re.compile(r"^## (User|Assistant|System)\s*$", re.MULTILINE)


class ThreadPersistence:
    def __init__(self, vault_root: Path, writer: VaultWriter, db: StateDB) -> None:
        self.vault_root = vault_root
        self.writer = writer
        self.db = db

    def thread_path(self, thread_id: str, config: ChatSessionConfig) -> Path:
        """Returns vault-relative path: <domains[0]>/chats/<thread_id>.md."""
        return Path(config.domains[0]) / "chats" / f"{thread_id}.md"

    def write(
        self,
        thread_id: str,
        config: ChatSessionConfig,
        turns: list[ChatTurn],
    ) -> Path:
        """Writes the thread via VaultWriter and upserts chat_threads."""
        rel = self.thread_path(thread_id, config)
        full = self.vault_root / rel
        body = self._render(thread_id=thread_id, config=config, turns=turns)
        if full.exists():
            old_body = full.read_text(encoding="utf-8")
            patch = PatchSet(
                edits=[Edit(path=full, old=old_body, new=body)],
                reason=f"chat turn {len(turns)}",
            )
        else:
            patch = PatchSet(
                new_files=[NewFile(path=full, content=body)],
                reason=f"chat thread {thread_id} created",
            )
        self.writer.apply(patch, allowed_domains=config.domains)

        cost = sum(t.cost_usd for t in turns)
        self.db.exec(
            "INSERT OR REPLACE INTO chat_threads"
            "(thread_id, path, domain, mode, turns, cost_usd, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                thread_id,
                rel.as_posix(),
                config.domains[0],
                config.mode.value,
                len(turns),
                cost,
                datetime.now(UTC).isoformat(),
            ),
        )
        return full

    def read(self, path: Path) -> LoadedThread:
        """Parses a thread file back from an absolute path."""
        raw = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        scope_str = str(fm.get("scope", ""))
        domains = tuple(d.strip() for d in scope_str.split(",") if d.strip())
        if not domains:
            domains = (path.parent.parent.name,)
        config = ChatSessionConfig(
            mode=ChatMode(str(fm["mode"])),
            domains=domains,
            model=str(fm.get("model", "claude-sonnet-4-6")),
        )
        updated_str = str(fm.get("updated", datetime.now(UTC).isoformat()))
        turn_time = datetime.fromisoformat(updated_str)
        turns: list[ChatTurn] = []
        for role_name, section in _split_sections(body):
            turns.append(
                ChatTurn(
                    role=TurnRole(role_name.lower()),
                    content=section,
                    created_at=turn_time,
                )
            )
        return LoadedThread(config=config, turns=turns)

    def _render(
        self,
        *,
        thread_id: str,
        config: ChatSessionConfig,
        turns: list[ChatTurn],
    ) -> str:
        now = datetime.now(UTC).isoformat()
        cost = sum(t.cost_usd for t in turns)
        created = turns[0].created_at.isoformat() if turns else now
        fm_block = (
            "---\n"
            f"mode: {config.mode.value}\n"
            f"scope: {','.join(config.domains)}\n"
            f"model: {config.model}\n"
            f"created: {created}\n"
            f"updated: {now}\n"
            f"turns: {len(turns)}\n"
            f"cost_usd: {cost}\n"
            "---\n\n"
            f"# {thread_id}\n\n"
        )
        headers = {
            "user": "## User",
            "assistant": "## Assistant",
            "system": "## System",
        }
        sections: list[str] = []
        for t in turns:
            header = headers[t.role.value]
            body_parts = [t.content.strip()]
            for call in t.tool_calls:
                name = str(call.get("name", "unknown"))
                args_json = json.dumps(call.get("args", {}), indent=2)
                result_preview = str(call.get("result_preview", ""))
                body_parts.append(f"```tool:{name}\n{args_json}\n```")
                body_parts.append(f"```tool-result:{name}\n{result_preview}\n```")
            sections.append(f"{header}\n\n" + "\n\n".join(body_parts))
        return fm_block + "\n\n".join(sections) + "\n"


def _split_sections(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((m.group(1), body[start:end].strip()))
    return out
