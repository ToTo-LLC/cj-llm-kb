"""FakeLLMProvider — queue-based stub for tests. No network calls ever.

## E2E backdoor (Plan 07 Task 25C)

Unit and integration tests prime the queue explicitly (the "empty queue =
programmer error, raise loudly" contract Plan 02 shipped with). Playwright
and the 14-gate demo run across a subprocess boundary where there is no
in-process ``llm.queue(...)`` call site — the FakeLLM lives inside the
spawned ``brain_api``, and the test driver talks to it only over HTTP/WS.

For those runs, the environment variable ``BRAIN_E2E_MODE=1`` switches the
empty-queue behavior from "raise" to "return a scripted canned response."
The canned responses are prompt-aware:

    * Classify prompts   → ``ClassifyOutput`` JSON, domain=work, conf=0.85
    * Summarize prompts  → ``SummarizeOutput`` JSON with a minimal body
    * Integrate prompts  → ``PatchSet`` JSON with one ``NewFile``
    * Chat / everything else → a plain-text greeting streamed as deltas

The env check is per-request (not cached at ``__init__``) so a single
process can flip the flag on for one block of work and off for another —
matters for tests that deliberately exercise the raise-on-empty path
while the outer harness has ``BRAIN_E2E_MODE`` exported.

Detection is heuristic: we sniff the prompt's system text for
identifying phrases ("Classify", "Summarize", "Integrate"). The
heuristic is good enough for the Plan 07 demo / e2e run; when we
eventually need tighter control a future iteration can add an
``ingest_fixture`` test hook to prime canned responses per tool.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from brain_core.llm.types import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
    ToolUse,
    ToolUseStart,
)


@dataclass
class _QueuedResponse:
    content: str
    input_tokens: int
    output_tokens: int
    tool_uses: list[ToolUse] = field(default_factory=list)
    stop_reason: str = "end_turn"


def _e2e_mode_enabled() -> bool:
    """Return True when ``BRAIN_E2E_MODE`` env var is set to a truthy value.

    We accept ``1``, ``true``, ``yes`` (case-insensitive) — anything else,
    including unset, counts as off. Read per call so a test can toggle
    the flag between requests.
    """
    val = os.environ.get("BRAIN_E2E_MODE", "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _pick_canned_response(request: LLMRequest) -> _QueuedResponse:
    """Return a prompt-aware canned response for E2E runs.

    The ingest pipeline calls ``llm.complete()`` with a distinct system
    prompt per stage (loaded from ``brain_core/prompts/*.txt``). We sniff
    the system prompt's first chunk to route to the right canned shape.
    Chat turns use ``llm.stream()`` with a mode prompt that doesn't match
    any of the sniff keywords, so they fall through to the text default.
    """
    system = (request.system or "").lower()
    # Classify: return valid ClassifyOutput JSON. Domain=work is the safe
    # pick because it's in every demo allowed_domains tuple, and the
    # Literal type in ClassifyOutput forbids any domain brain_core doesn't
    # recognize — returning "test-only" here would crash model_validate_json.
    if "classify" in system or "source_type" in system:
        payload = {
            "source_type": "text",
            "domain": "work",
            "confidence": 0.85,
        }
        return _QueuedResponse(
            content=json.dumps(payload),
            input_tokens=50,
            output_tokens=30,
        )
    # Summarize: SummarizeOutput JSON. Short lists so the source-note
    # renderer has content to render without looking suspicious.
    if "summarize" in system or "summary" in system:
        payload = {
            "title": "E2E Test Source",
            "summary": "This is a canned summary for E2E mode.",
            "key_points": ["Point one.", "Point two."],
            "entities": ["brain"],
            "concepts": ["testing"],
            "open_questions": [],
        }
        return _QueuedResponse(
            content=json.dumps(payload),
            input_tokens=200,
            output_tokens=120,
        )
    # Integrate: PatchSet JSON. A minimal single-file patch the pipeline
    # will prepend a source note to.
    if "integrate" in system or "patchset" in system or "new_files" in system:
        payload = {
            "new_files": [],
            "edits": [],
            "index_entries": [],
            "log_entry": "e2e canned integrate",
            "reason": "e2e mode canned response",
            "category": "ingest",
        }
        return _QueuedResponse(
            content=json.dumps(payload),
            input_tokens=200,
            output_tokens=80,
        )
    # Autotitle: ChatAutotitleOutput JSON.
    if "autotitle" in system or ("title" in system and "slug" in system):
        payload = {"title": "E2E Thread", "slug": "e2e-thread"}
        return _QueuedResponse(
            content=json.dumps(payload),
            input_tokens=30,
            output_tokens=20,
        )
    # Fallback — chat turn or anything else: greet the user with a
    # predictable string the WS transcript + Playwright assertions can
    # match on.
    return _QueuedResponse(
        content="Hello from FakeLLM. (E2E mode default reply.)",
        input_tokens=40,
        output_tokens=12,
    )


class FakeLLMProvider:
    name = "fake"

    def __init__(self) -> None:
        self._queue: list[_QueuedResponse] = []
        self.requests: list[LLMRequest] = []

    def queue(self, content: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Queue a plain-text response (Plan 02 shape; stop_reason='end_turn')."""
        self._queue.append(
            _QueuedResponse(content=content, input_tokens=input_tokens, output_tokens=output_tokens)
        )

    def queue_tool_use(
        self,
        tool_uses: list[ToolUse],
        *,
        text: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Queue a response that emits tool_use blocks (stop_reason='tool_use')."""
        self._queue.append(
            _QueuedResponse(
                content=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_uses=list(tool_uses),
                stop_reason="tool_use",
            )
        )

    def _pop_or_canned(self, request: LLMRequest) -> _QueuedResponse:
        """Return the next queued response, or a canned one in E2E mode.

        Outside E2E mode this is just ``self._queue.pop(0)`` and an
        empty queue raises RuntimeError — the Plan 02 contract unit
        tests still rely on. Inside E2E mode, an empty queue falls back
        to a prompt-aware canned response.
        """
        if self._queue:
            return self._queue.pop(0)
        if _e2e_mode_enabled():
            return _pick_canned_response(request)
        raise RuntimeError(
            "FakeLLMProvider queue is empty — call .queue() or .queue_tool_use() first"
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        q = self._pop_or_canned(request)
        return LLMResponse(
            model=request.model,
            content=q.content,
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            stop_reason=q.stop_reason,
            tool_uses=list(q.tool_uses),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        q = self._pop_or_canned(request)
        for ch in q.content:
            yield LLMStreamChunk(delta=ch)
        for tu in q.tool_uses:
            yield LLMStreamChunk(tool_use_start=ToolUseStart(id=tu.id, name=tu.name))
            yield LLMStreamChunk(tool_use_input_delta=json.dumps(tu.input))
            yield LLMStreamChunk(tool_use_stop_id=tu.id)
        yield LLMStreamChunk(
            usage=TokenUsage(input_tokens=q.input_tokens, output_tokens=q.output_tokens),
            done=True,
        )
