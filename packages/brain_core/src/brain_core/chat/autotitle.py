"""Auto-title: after turn 2, ask a cheap LLM to summarize the thread in 3-6 words.

The result is used by ChatSession (Task 18) to rename the chat thread file from
a draft id like '2026-04-14-draft-abc123' to '2026-04-14-karpathy-llm-wiki-xyz'.

Uses the cheapest available model (Haiku) via the LLMProvider abstraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from brain_core.chat.types import ChatTurn
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import Prompt, load_prompt


class AutoTitleError(ValueError):
    """Raised when the LLM response cannot be parsed into a valid title+slug."""


@dataclass(frozen=True)
class AutoTitleResult:
    title: str
    slug: str


class AutoTitler:
    """Produces a short kebab-case title for a chat thread from its first two turns."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        prompt: Prompt | None = None,
        model: str = "claude-haiku-4-5",
    ) -> None:
        self.llm = llm
        self.prompt = prompt if prompt is not None else load_prompt("chat_autotitle")
        self.model = model

    async def run(self, turns: list[ChatTurn]) -> AutoTitleResult:
        """Run the auto-titler against the first two turns of a thread."""
        if len(turns) < 2:
            raise AutoTitleError(f"autotitle requires at least 2 turns, got {len(turns)}")
        turns_text = "\n\n".join(f"{t.role}: {t.content}" for t in turns[:2])
        user_content = self.prompt.render(turns=turns_text)
        request = LLMRequest(
            model=self.model,
            system=self.prompt.system,
            messages=[LLMMessage(role="user", content=user_content)],
            max_tokens=64,
            temperature=0.2,
        )
        response = await self.llm.complete(request)
        return self._parse(response.content)

    def _parse(self, raw: str) -> AutoTitleResult:
        stripped = raw.strip()
        # Strip common code-fence wrappers that Haiku sometimes adds.
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            lines = lines[1:]  # drop opening fence (e.g. ```json)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # drop closing fence
            stripped = "\n".join(lines).strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AutoTitleError(f"autotitle returned non-JSON: {stripped[:100]}") from exc
        if not isinstance(data, dict):
            raise AutoTitleError(f"autotitle expected JSON object, got {type(data).__name__}")
        title = str(data.get("title", "")).strip()
        if not title:
            raise AutoTitleError(f"autotitle missing title: {data}")
        # Derive slug deterministically from title — ignore any slug the LLM returned.
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            raise AutoTitleError(f"autotitle title {title!r} produced empty slug")
        return AutoTitleResult(title=title, slug=slug)
