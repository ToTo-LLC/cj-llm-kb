"""ChatSession — async event loop for a single chat thread.

Task 17 scope: pure event loop. No persistence, no autotitle, no vault mutation
wiring beyond what tools do on their own. Task 18 layers persistence on top.

The session maintains in-memory turn history and a dict of notes loaded via the
read_note tool so subsequent turns' compiled context sees them. Mutator helpers
(switch_mode, switch_scope, set_open_doc) rebuild the effective (mode-filtered)
tool registry so the next turn uses the right toolset.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brain_core.chat.autotitle import AutoTitler
from brain_core.chat.context import ContextCompiler
from brain_core.chat.modes import MODES, tool_to_tooldef
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.tools.base import ToolContext, ToolRegistry
from brain_core.chat.types import (
    ChatEvent,
    ChatEventKind,
    ChatMode,
    ChatSessionConfig,
    ChatTurn,
    TurnRole,
)
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import (
    ContentBlock,
    LLMMessage,
    LLMRequest,
    TextBlock,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
)
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter

logger = logging.getLogger(__name__)

# Plan 07 Task 2: Draft-mode structured-edit fence. The assistant may
# append one or more ``\`\`\`edits\n{...}\n\`\`\`` blocks to its reply.
# Each block's JSON body is ``{"edits": [ {op, anchor, text?}, ... ]}``.
# ``re.DOTALL`` so the body may contain newlines; non-greedy so
# adjacent fences don't collapse into one match.
_EDITS_FENCE_RE = re.compile(r"```edits\s*\n(.+?)\n```", re.DOTALL)


class ChatSession:
    """Async chat loop. One instance per thread. Not thread-safe."""

    MAX_TOOL_ROUNDS = 10

    def __init__(
        self,
        *,
        config: ChatSessionConfig,
        llm: LLMProvider,
        compiler: ContextCompiler,
        registry: ToolRegistry,
        retrieval: BM25VaultIndex | None,
        pending_store: PendingPatchStore | None,
        state_db: StateDB | None,
        vault_root: Path,
        thread_id: str,
        persistence: ThreadPersistence | None = None,
        autotitler: AutoTitler | None = None,
        vault_writer: VaultWriter | None = None,
        initial_turns: list[ChatTurn] | None = None,
        cost_ledger: CostLedger | None = None,
    ) -> None:
        if autotitler is not None and vault_writer is None:
            raise ValueError("autotitler requires vault_writer")
        self.config = config
        self.llm = llm
        self.compiler = compiler
        self.registry = registry
        self.retrieval = retrieval
        self.pending_store = pending_store
        self.state_db = state_db
        self.vault_root = vault_root
        self.thread_id = thread_id
        self.persistence = persistence
        self.autotitler = autotitler
        self.vault_writer = vault_writer
        # Plan 07 Task 3: optional CostLedger. When present, the session
        # writes a ``CostEntry`` tagged with ``mode=self.config.mode.value``
        # after every successful turn so the Plan 07 UI can break spend
        # down by chat surface. ``None`` preserves Plan 03 semantics
        # (session loop does not write to the ledger).
        self.cost_ledger = cost_ledger
        # ``initial_turns`` rehydrates an existing thread — the list is
        # copied so mutations during subsequent turns don't leak back to
        # the caller. Plan 05 Task 21 uses this to reconstruct a chat
        # session from ``ThreadPersistence.read(path).turns`` on WS
        # reconnect. ``None`` (the default) starts with an empty history,
        # preserving the Plan 03 constructor semantics.
        self._turns: list[ChatTurn] = list(initial_turns) if initial_turns else []
        self._read_notes: dict[Path, str] = {}
        self._effective_registry = self._build_effective_registry()

    @property
    def turn_count(self) -> int:
        """Number of user turns in the session (1 per completed turn).

        Plan 05 Task 21 reports this in the WS ``thread_loaded`` frame on
        reconnect. We count USER-role turns (not total entries) because
        each completed turn is one user message + one assistant message;
        the conceptual "turn" in the chat UI maps 1:1 to user messages.
        SYSTEM entries (mode/scope/open-doc change markers) are excluded
        so they don't inflate the count surfaced to the client.
        """
        return sum(1 for t in self._turns if t.role == TurnRole.USER)

    # ----- registry / mutators ------------------------------------------------

    def _build_effective_registry(self) -> ToolRegistry:
        mode_allowlist = MODES[self.config.mode].tool_allowlist
        allowlist = mode_allowlist
        if self.config.open_doc_path is None:
            allowlist = tuple(name for name in mode_allowlist if name != "edit_open_doc")
        return self.registry.subset(allowlist=allowlist)

    def switch_mode(self, new_mode: ChatMode) -> None:
        """Swap the chat mode and rebuild the effective tool registry."""
        if new_mode == self.config.mode:
            return
        old = self.config.mode
        self.config = self.config.model_copy(update={"mode": new_mode})
        self._effective_registry = self._build_effective_registry()
        self._turns.append(
            ChatTurn(
                role=TurnRole.SYSTEM,
                content=f"mode changed: {old.value} -> {new_mode.value}",
                created_at=datetime.now(UTC),
            )
        )

    def switch_scope(self, new_domains: tuple[str, ...]) -> None:
        """Swap the allowed-domain scope and rebuild retrieval if present."""
        if new_domains == self.config.domains:
            return
        old = self.config.domains
        self.config = self.config.model_copy(update={"domains": new_domains})
        if self.retrieval is not None:
            self.retrieval.build(new_domains)
        self._turns.append(
            ChatTurn(
                role=TurnRole.SYSTEM,
                content=f"scope changed: {','.join(old)} -> {','.join(new_domains)}",
                created_at=datetime.now(UTC),
            )
        )

    def set_open_doc(self, path: Path | None) -> None:
        """Set or clear the open doc path and rebuild the effective registry."""
        old = self.config.open_doc_path
        if old == path:
            return
        self.config = self.config.model_copy(update={"open_doc_path": path})
        self._effective_registry = self._build_effective_registry()
        if old is None and path is not None:
            content = f"open doc set: {path.as_posix()}"
        elif old is not None and path is None:
            content = f"open doc cleared (was: {old.as_posix()})"
        else:
            assert old is not None and path is not None
            content = f"open doc changed: {old.as_posix()} -> {path.as_posix()}"
        self._turns.append(
            ChatTurn(
                role=TurnRole.SYSTEM,
                content=content,
                created_at=datetime.now(UTC),
            )
        )

    # ----- turn loop ----------------------------------------------------------

    async def turn(self, user_message: str) -> AsyncIterator[ChatEvent]:
        """Run one chat turn. Yields events; appends to self._turns at the end."""
        turn_cost = 0.0
        # Plan 07 Task 3: accumulate token usage across rounds so the
        # final COST_UPDATE event carries real numbers for the WS
        # ``cumulative_tokens_in`` gauge. ``TokenUsage`` may be absent
        # on a round (FakeLLM stubs, providers that don't report usage)
        # — we treat that as 0 to avoid double-counting against whatever
        # the previous round reported.
        turn_tokens_in = 0
        turn_tokens_out = 0
        tool_call_records: list[dict[str, Any]] = []
        compiled = self.compiler.compile(
            config=self.config,
            turns=self._turns,
            read_notes=self._read_notes,
            user_message=user_message,
        )
        messages: list[LLMMessage] = [LLMMessage(**m) for m in compiled.messages]
        final_text_parts: list[str] = []

        # Plan 07 Task 2: per-mode model override. ``ChatSessionConfig``
        # exposes ``ask_model`` / ``brainstorm_model`` / ``draft_model``;
        # when the active mode's field is set it wins, otherwise we fall
        # back to ``config.model`` (Plan 03 default-model semantics).
        # Auto-titling at the end of the turn keeps using ``config.model``
        # (see ``AutoTitler`` wiring); auto-title is mode-independent.
        mode_model_attr = f"{self.config.mode.value}_model"
        turn_model = getattr(self.config, mode_model_attr, None) or self.config.model

        try:
            # Rounds 0..MAX-1 do real work; round MAX is the sentinel cap
            # check that bails out with "max tool rounds exceeded".
            for round_idx in range(self.MAX_TOOL_ROUNDS + 1):
                if round_idx == self.MAX_TOOL_ROUNDS:
                    yield ChatEvent(
                        kind=ChatEventKind.TURN_END,
                        data={
                            "text": "".join(final_text_parts),
                            "cost_usd": turn_cost,
                            "error": "max tool rounds exceeded",
                        },
                    )
                    return

                request = LLMRequest(
                    model=turn_model,
                    system=compiled.system,
                    messages=messages,
                    temperature=MODES[self.config.mode].temperature,
                    tools=[tool_to_tooldef(t) for t in self._effective_registry.all()],
                    max_tokens=4096,
                )

                pending_tool_uses: list[dict[str, Any]] = []
                current_text_parts: list[str] = []
                round_usage: TokenUsage | None = None

                async for chunk in self.llm.stream(request):
                    if chunk.delta:
                        current_text_parts.append(chunk.delta)
                        yield ChatEvent(
                            kind=ChatEventKind.DELTA,
                            data={"text": chunk.delta},
                        )
                    if chunk.tool_use_start is not None:
                        pending_tool_uses.append(
                            {
                                "id": chunk.tool_use_start.id,
                                "name": chunk.tool_use_start.name,
                                "input_json": "",
                            }
                        )
                    if chunk.tool_use_input_delta is not None and pending_tool_uses:
                        pending_tool_uses[-1]["input_json"] += chunk.tool_use_input_delta
                    if chunk.usage is not None:
                        round_usage = chunk.usage
                    if chunk.done:
                        break

                # Cost pricing not owned by the session loop — Task 18 may plug
                # in brain_core.cost. round_usage is observable but not priced.
                # Plan 07 Task 3: accumulate token counts for the final
                # COST_UPDATE event so the WS ``cumulative_tokens_in``
                # gauge sees real numbers. Pricing (``turn_cost``) is
                # still deferred to the Task 21+ ledger wiring.
                if round_usage is not None:
                    turn_tokens_in += round_usage.input_tokens
                    turn_tokens_out += round_usage.output_tokens

                if not pending_tool_uses:
                    round_text = "".join(current_text_parts)
                    final_text_parts.append(round_text)
                    yield ChatEvent(
                        kind=ChatEventKind.COST_UPDATE,
                        data={
                            "turn_cost_usd": turn_cost,
                            "session_cost_usd": turn_cost,
                            "tokens_in": turn_tokens_in,
                            "tokens_out": turn_tokens_out,
                        },
                    )
                    break

                # Build assistant message with text + tool_use blocks.
                assistant_blocks: list[ContentBlock] = []
                if current_text_parts:
                    assistant_blocks.append(TextBlock(text="".join(current_text_parts)))
                parsed_inputs: list[dict[str, Any]] = []
                for tu in pending_tool_uses:
                    try:
                        parsed = json.loads(tu["input_json"]) if tu["input_json"] else {}
                    except json.JSONDecodeError:
                        parsed = {}
                    parsed_inputs.append(parsed)
                    assistant_blocks.append(
                        ToolUseBlock(id=tu["id"], name=tu["name"], input=parsed)
                    )
                messages.append(LLMMessage(role="assistant", content=assistant_blocks))
                final_text_parts.append("".join(current_text_parts))

                # Dispatch each tool and collect tool_result blocks.
                tool_result_blocks: list[ContentBlock] = []
                for tu, parsed_input in zip(pending_tool_uses, parsed_inputs, strict=True):
                    yield ChatEvent(
                        kind=ChatEventKind.TOOL_CALL,
                        data={
                            "id": tu["id"],
                            "name": tu["name"],
                            "args": parsed_input,
                        },
                    )
                    try:
                        tool = self._effective_registry.get(tu["name"])
                    except KeyError:
                        error_text = f"tool {tu['name']!r} not available in this mode"
                        tool_result_blocks.append(
                            ToolResultBlock(
                                tool_use_id=tu["id"],
                                content=error_text,
                                is_error=True,
                            )
                        )
                        yield ChatEvent(
                            kind=ChatEventKind.TOOL_RESULT,
                            data={
                                "id": tu["id"],
                                "name": tu["name"],
                                "text": error_text,
                                "error": True,
                            },
                        )
                        tool_call_records.append(
                            {
                                "name": tu["name"],
                                "args": parsed_input,
                                "result_preview": error_text,
                                "error": True,
                            }
                        )
                        continue

                    ctx = ToolContext(
                        vault_root=self.vault_root,
                        allowed_domains=self.config.domains,
                        open_doc_path=self.config.open_doc_path,
                        retrieval=self.retrieval,
                        pending_store=self.pending_store,
                        state_db=self.state_db,
                        source_thread=self.thread_id,
                        mode_name=self.config.mode.value,
                    )
                    try:
                        result = tool.run(parsed_input, ctx)
                    except Exception as exc:
                        error_text = f"{type(exc).__name__}: {exc}"
                        tool_result_blocks.append(
                            ToolResultBlock(
                                tool_use_id=tu["id"],
                                content=error_text,
                                is_error=True,
                            )
                        )
                        yield ChatEvent(
                            kind=ChatEventKind.TOOL_RESULT,
                            data={
                                "id": tu["id"],
                                "name": tu["name"],
                                "text": error_text,
                                "error": True,
                            },
                        )
                        tool_call_records.append(
                            {
                                "name": tu["name"],
                                "args": parsed_input,
                                "result_preview": error_text,
                                "error": True,
                            }
                        )
                        continue

                    if (
                        tu["name"] == "read_note"
                        and result.data
                        and "path" in result.data
                        and "body" in result.data
                    ):
                        self._read_notes[Path(str(result.data["path"]))] = str(result.data["body"])

                    tool_result_blocks.append(
                        ToolResultBlock(
                            tool_use_id=tu["id"],
                            content=result.text,
                            is_error=False,
                        )
                    )
                    yield ChatEvent(
                        kind=ChatEventKind.TOOL_RESULT,
                        data={
                            "id": tu["id"],
                            "name": tu["name"],
                            "text": result.text,
                        },
                    )
                    if result.proposed_patch is not None:
                        yield ChatEvent(
                            kind=ChatEventKind.PATCH_PROPOSED,
                            data={
                                "patch_id": result.proposed_patch.patch_id,
                                "target_path": str(result.proposed_patch.target_path),
                                "tool": tu["name"],
                            },
                        )
                    tool_call_records.append(
                        {
                            "name": tu["name"],
                            "args": parsed_input,
                            "result_preview": result.text[:200],
                        }
                    )

                messages.append(LLMMessage(role="user", content=tool_result_blocks))

            # Plan 07 Task 2: Draft-mode ``\`\`\`edits`` fence → DOC_EDIT events.
            # Scan the assembled assistant message AFTER the stream has
            # finished. Non-Draft modes skip this entirely — the fence is
            # just text in their transcripts. Malformed JSON is logged and
            # skipped so a bad model response never breaks the turn.
            if self.config.mode == ChatMode.DRAFT:
                assistant_text = "".join(final_text_parts)
                for match in _EDITS_FENCE_RE.finditer(assistant_text):
                    body = match.group(1)
                    try:
                        parsed = json.loads(body)
                    except json.JSONDecodeError as exc:
                        logger.warning("draft edits fence has invalid JSON: %s", exc)
                        continue
                    if not isinstance(parsed, dict):
                        logger.warning("draft edits fence JSON is not an object: %r", type(parsed))
                        continue
                    edits = parsed.get("edits")
                    if not isinstance(edits, list):
                        logger.warning("draft edits fence missing 'edits' list: %r", parsed)
                        continue
                    for edit in edits:
                        if not isinstance(edit, dict):
                            logger.warning("draft edits entry is not an object: %r", edit)
                            continue
                        yield ChatEvent(
                            kind=ChatEventKind.DOC_EDIT,
                            data=dict(edit),
                        )

            yield ChatEvent(
                kind=ChatEventKind.TURN_END,
                data={"text": "".join(final_text_parts), "cost_usd": turn_cost},
            )

        except Exception as exc:
            yield ChatEvent(
                kind=ChatEventKind.ERROR,
                data={"message": f"{type(exc).__name__}: {exc}"},
            )
            raise
        finally:
            # Partial turns (on exception) are intentionally persisted for
            # debugging; cost=0 on the user turn, cost accumulated so far on
            # the assistant turn even when the body is empty.
            now = datetime.now(UTC)
            self._turns.append(
                ChatTurn(
                    role=TurnRole.USER,
                    content=user_message,
                    created_at=now,
                    cost_usd=0.0,
                )
            )
            self._turns.append(
                ChatTurn(
                    role=TurnRole.ASSISTANT,
                    content="".join(final_text_parts),
                    created_at=now,
                    tool_calls=tool_call_records,
                    cost_usd=turn_cost,
                )
            )

        # Task 18: persistence + autotitle. Runs only on successful turn
        # completion (the finally re-raises exceptions before reaching here).
        if self.persistence is not None:
            self.persistence.write(
                thread_id=self.thread_id,
                config=self.config,
                turns=self._turns,
            )

        # Plan 07 Task 3: record the turn against the cost ledger, tagged
        # with the chat mode so the Plan 07 UI can break spend down by
        # surface (``ask`` / ``brainstorm`` / ``draft``). Tagged with the
        # first allowed domain as a best-effort proxy — chat is scoped
        # across all allowed domains, not a single one, but the ledger's
        # ``domain`` column is required and must not be blank.
        if self.cost_ledger is not None:
            chat_domain = self.config.domains[0] if self.config.domains else "unknown"
            self.cost_ledger.record(
                CostEntry(
                    timestamp=datetime.now(UTC),
                    operation="chat_turn",
                    model=turn_model,
                    input_tokens=turn_tokens_in,
                    output_tokens=turn_tokens_out,
                    cost_usd=turn_cost,
                    domain=chat_domain,
                    mode=self.config.mode.value,
                )
            )

        user_turn_count = sum(1 for t in self._turns if t.role == TurnRole.USER)
        if (
            self.autotitler is not None
            and self.vault_writer is not None
            and self.persistence is not None
            and user_turn_count == 2
            and "draft" in self.thread_id
        ):
            try:
                title_result = await self.autotitler.run(self._turns)
            except Exception as exc:
                yield ChatEvent(
                    kind=ChatEventKind.ERROR,
                    data={"message": f"autotitle failed: {exc}"},
                )
                return

            old_thread_id = self.thread_id
            date_prefix = old_thread_id[:10]
            short_suffix = old_thread_id.split("-")[-1][:6]
            new_thread_id = f"{date_prefix}-{title_result.slug}-{short_suffix}"

            old_rel = self.persistence.thread_path(old_thread_id, self.config)
            new_rel = self.persistence.thread_path(new_thread_id, self.config)
            old_abs = self.vault_root / old_rel
            new_abs = self.vault_root / new_rel

            try:
                self.vault_writer.rename_file(old_abs, new_abs, allowed_domains=self.config.domains)
            except Exception as exc:
                yield ChatEvent(
                    kind=ChatEventKind.ERROR,
                    data={"message": f"autotitle rename failed: {exc}"},
                )
                return

            self.thread_id = new_thread_id
            # Vault write first, then state.sqlite DELETE — a crash between
            # the two leaves an orphan row that `brain doctor --rebuild-cache`
            # would clean up (CLAUDE.md principle #6: vault is the source of
            # truth; SQLite is a rebuildable cache).
            if self.state_db is not None:
                self.state_db.exec(
                    "DELETE FROM chat_threads WHERE thread_id = ?",
                    (old_thread_id,),
                )
            self.persistence.write(
                thread_id=self.thread_id,
                config=self.config,
                turns=self._turns,
            )
