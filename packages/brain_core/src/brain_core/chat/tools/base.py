"""ChatTool Protocol + ToolRegistry.

Bottom-of-graph module: imports only stdlib + typing. `retrieval`, `pending_store`,
and `state_db` fields on ToolContext are typed as Any to avoid creating import
cycles with the modules that provide those types — each concrete tool in
tools/*.py will narrow the type at use site if needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, runtime_checkable


@dataclass(frozen=True)
class ToolContext:
    vault_root: Path
    allowed_domains: tuple[str, ...]
    open_doc_path: Path | None
    retrieval: Any
    pending_store: Any | None
    state_db: Any | None
    source_thread: str
    mode_name: str


@dataclass(frozen=True)
class ToolResult:
    text: str
    data: dict[str, Any] | None = None
    proposed_patch: Any | None = None


@runtime_checkable
class ChatTool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ChatTool] = {}

    def register(self, tool: ChatTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ChatTool:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def all(self) -> list[ChatTool]:
        return list(self._tools.values())

    def subset(self, allowlist: tuple[str, ...]) -> Self:
        # Construct a new empty registry without going through register(),
        # which would re-enforce the duplicate-check unnecessarily.
        filtered = type(self)()
        for name in allowlist:
            if name in self._tools:
                filtered._tools[name] = self._tools[name]
        return filtered
