"""read_note tool - scope-guarded note reader.

Returns the body as text plus the parsed frontmatter in data. Rejects absolute
paths explicitly (vault-relative only), leans on scope_guard for domain checking,
and raises FileNotFoundError with a plain-English message on missing files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter
from brain_core.vault.paths import scope_guard


class ReadNoteTool:
    name = "read_note"
    description = "Read a note by vault-relative path. Returns frontmatter + body."
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raw = str(args["path"])
        p = Path(raw)
        if p.is_absolute():
            raise ValueError("path must be vault-relative, not absolute")
        full = scope_guard(
            ctx.vault_root / p,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not full.exists():
            raise FileNotFoundError(f"note {raw!r} not found in vault")
        text = full.read_text(encoding="utf-8")
        try:
            fm, body = parse_frontmatter(text)
        except FrontmatterError:
            fm, body = {}, text
        return ToolResult(
            text=body,
            data={"frontmatter": fm, "body": body, "path": p.as_posix()},
        )
