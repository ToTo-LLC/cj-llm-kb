"""Source type dispatcher — picks the right handler for a given spec.

Handler order matters: more specific handlers must come first so that e.g.
Tweet URLs beat the generic URL handler, and transcript-style inputs beat
plain text. The order is codified in `_default_handlers()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from brain_core.ingest.handlers.base import SourceHandler
from brain_core.ingest.handlers.email import EmailHandler
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.handlers.transcript_docx import TranscriptDOCXHandler
from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
from brain_core.ingest.handlers.transcript_vtt import TranscriptVTTHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler

if TYPE_CHECKING:
    from brain_core.config.schema import HandlersConfig


class DispatchError(RuntimeError):
    """No handler could claim the given source spec."""


def _default_handlers(cfg: HandlersConfig | None = None) -> list[SourceHandler]:
    """Ordered list of handlers. More-specific must come before more-general.

    - TweetHandler before URLHandler: tweet URLs also match the generic URL
      handler; tweet must win.
    - Transcript handlers (vtt, docx, text) before PDFHandler/EmailHandler/TextHandler:
      they target more specific extensions or stem conventions.
    - TextHandler is last: it's the broadest file-level catch.

    ``cfg`` (issue #23) feeds per-handler tunables (URL/Tweet timeouts, PDF
    min_chars). When ``None`` every handler uses its constructor default —
    matches pre-issue-#23 behavior bit-for-bit so tests + embedders that
    construct handlers without a config keep working.
    """
    return [
        TweetHandler(timeout_seconds=cfg.tweet.timeout_seconds) if cfg else TweetHandler(),
        URLHandler(timeout_seconds=cfg.url.timeout_seconds) if cfg else URLHandler(),
        TranscriptVTTHandler(),
        TranscriptDOCXHandler(),
        TranscriptTextHandler(),
        PDFHandler(min_chars=cfg.pdf.min_chars) if cfg else PDFHandler(),
        EmailHandler(),
        TextHandler(),
    ]


async def dispatch(
    spec: str | Path,
    *,
    handlers: list[SourceHandler] | None = None,
) -> SourceHandler:
    """Return the first handler that claims `spec`, or raise DispatchError.

    `dispatch` is async for pipeline consistency (the ingest pipeline is async
    end-to-end), but `can_handle` itself is synchronous per the Protocol.
    """
    candidates = handlers or _default_handlers()
    for h in candidates:
        if h.can_handle(spec):
            return h
    raise DispatchError(f"no handler claimed {spec!r}")
