"""GET /api/bulk/walk-progress — Plan 26 T3.

Server-Sent Events stream that drives real walk-phase progress in the
bulk-import wizard. Pre-T3 the wizard ran a timer-based pseudo-progress
animation while it waited for the (synchronous) walk to return; T3
replaces that pseudo-progress with this stream so the bar moves to the
beat of actual filesystem scanning.

Wire format: one ``data: <json>\\n\\n`` SSE record per event, where
``<json>`` is :meth:`pydantic.BaseModel.model_dump_json` output for one
of the four :class:`~brain_core.ingest.walk_events.WalkEvent` subclasses
(``walk_started``, ``walk_progress``, ``walk_complete``, ``walk_error``).

Safety rails:

- ``OriginHostMiddleware`` (the app-wide ASGI middleware) rejects any
  non-loopback ``Host`` header. SSE is HTTP GET so the middleware's
  "safe methods skip Origin check" branch applies — we layer an
  explicit Origin check at the endpoint level via
  :func:`require_loopback_origin`, mirroring ``/api/setup-status``.
- ``X-Brain-Token`` cannot ride on the EventSource constructor (the
  browser API allows neither custom headers nor cookies on a
  cross-origin EventSource). We use the same query-param convention
  ``check_ws_token`` uses for the chat WebSocket: ``?token=<hex>``.
- Path validation runs BEFORE switching to streaming. Invalid paths
  return 400 with the flat error envelope (``error``, ``message``,
  ``detail``). Once the response starts streaming we cannot change
  the status code.

Decisions: see ``tasks/plans/26-critical-fix-and-plan-25-aftermath.md``
D3 (SSE not WS), D6 (event types), D7 (cancellation), D8 (auth), D9
(50-file flood control), D14 (stdlib-only — no ``sse-starlette``).
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from brain_core.ingest.bulk import BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from brain_api.context import AppContext, get_ctx
from brain_api.endpoints._origin import require_loopback_origin
from brain_api.errors import ApiError

router = APIRouter(tags=["bulk"])

_logger = structlog.get_logger(__name__)


def _check_sse_token(query_token: str | None, ctx_token: str | None) -> None:
    """Validate the ``?token=<hex>`` query param in constant time.

    The browser EventSource constructor accepts neither custom headers
    nor cookies, so the SSE channel inherits the same "token in the
    query string" convention :func:`brain_api.auth.check_ws_token`
    uses for the chat WebSocket. Mismatch raises a 403 ``refused``
    BEFORE the streaming response starts so the client sees a normal
    HTTP error envelope rather than an empty event-stream.
    """
    received = query_token or ""
    expected = ctx_token or ""
    if (
        not received
        or not expected
        or not secrets.compare_digest(received, expected)
    ):
        raise ApiError(
            status=403,
            code="refused",
            message="missing or invalid token query parameter",
        )


def _validate_path(raw_path: str, vault_root: Path) -> Path:
    """Reject empty / non-existent / non-directory inputs with 400.

    Returns the resolved :class:`pathlib.Path`. The endpoint hands
    this to :meth:`BulkImporter.plan_streaming` directly — we resolve
    via ``Path(raw_path)`` (no ``.resolve()``) to preserve the
    user-visible string in the emitted :class:`WalkStarted.path`.

    There is intentionally no "must live under vault_root" check: the
    bulk-import wizard accepts ARBITRARY source folders (the whole
    point of bulk import is to ingest content from outside the vault).
    ``vault_root`` is plumbed in only so a future hardening pass has a
    seam to layer on a deny-the-vault-tree check; today the parameter
    is unused. We do reject obviously hostile inputs (empty string).
    """
    del vault_root  # reserved for future deny-list checks
    if not raw_path:
        raise ApiError(
            status=400,
            code="invalid_input",
            message="path query parameter is required",
        )
    candidate = Path(raw_path)
    if not candidate.exists():
        raise ApiError(
            status=400,
            code="invalid_input",
            message=f"path does not exist: {raw_path}",
        )
    if not candidate.is_dir():
        raise ApiError(
            status=400,
            code="invalid_input",
            message=f"path is not a directory: {raw_path}",
        )
    return candidate


def _build_importer(ctx: AppContext) -> BulkImporter:
    """Construct a :class:`BulkImporter` wired to the live AppContext.

    The streaming walk path does not classify or extract — it only
    needs the dispatcher's handler list (for the claim check) and the
    pipeline's slug helper. We reuse the same recipe brain_core uses
    everywhere else so a future ``handlers``-config change ripples
    through automatically.
    """
    tool_ctx = ctx.tool_ctx
    pipeline = IngestPipeline(
        vault_root=ctx.vault_root,
        writer=tool_ctx.writer,
        llm=tool_ctx.llm,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )
    return BulkImporter(pipeline)


async def _event_stream(
    importer: BulkImporter,
    source_root: Path,
) -> AsyncIterator[bytes]:
    """Translate :class:`WalkEvent` objects into framed SSE bytes.

    Each event becomes one ``data: <json>\\n\\n`` record. Bytes (not
    str) so :class:`StreamingResponse` can send them straight through
    without an additional encode step.

    Cancellation surfaces as :class:`asyncio.CancelledError` from the
    underlying async generator (the ASGI server raises it when the
    client closes the connection). We log + re-raise so the request
    scope can finalize cleanly; the outer ``StreamingResponse``
    handles the actual close on the socket.

    Exceptions from the walk are NOT re-raised here: the inner
    generator already yields a ``WalkError`` frame, and re-raising
    after that frame is on the wire would cause :class:`StreamingResponse`
    to surface a 500 the client cannot meaningfully receive (the
    response has already started). Log + return cleanly instead.
    """
    try:
        async for event in importer.plan_streaming(source_root):
            yield f"data: {event.model_dump_json()}\n\n".encode()
    except asyncio.CancelledError:
        _logger.info(
            "bulk_walk_progress_cancelled",
            source_root=str(source_root),
        )
        raise
    except Exception as exc:
        # The walk-error frame is already on the wire (the inner generator
        # yields it before raising). Logging here keeps the failure
        # observable server-side; we do NOT re-raise so the response
        # closes with the events the client already received.
        _logger.warning(
            "bulk_walk_progress_failed",
            source_root=str(source_root),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return


@router.get(
    "/api/bulk/walk-progress",
    dependencies=[Depends(require_loopback_origin)],
    summary="SSE stream of walk-phase progress for the bulk-import wizard.",
)
async def stream_walk_progress(
    request: Request,
    path: str = Query(..., description="Absolute path to the folder to walk."),
    token: str = Query(..., description="App secret; mirrors the chat WS auth."),
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI Depends idiom
) -> StreamingResponse:
    """Open an event-stream that emits real walk-phase progress.

    Returns ``text/event-stream`` with one ``data: <json>\\n\\n`` record
    per event. On invalid input (bad path, missing/wrong token) returns
    a normal JSON error envelope BEFORE the streaming starts.

    The stream is read-only — no vault mutation, no LLM calls. The
    server's only state is the in-process walk; cancellation by the
    client cleanly tears it down via :class:`asyncio.CancelledError`.
    """
    # Use ``request`` to keep mypy / unused-arg checkers quiet — and as
    # a future seam for reading request_id / correlation headers.
    _ = request

    _check_sse_token(token, ctx.token)
    source_root = _validate_path(path, ctx.vault_root)
    importer = _build_importer(ctx)

    return StreamingResponse(
        _event_stream(importer, source_root),
        media_type="text/event-stream",
        headers={
            # Prevent intermediaries (and the browser's default cache)
            # from buffering the stream. Even on localhost a buffering
            # proxy (rare but possible) would defeat the whole point of
            # SSE — explicit headers cost nothing.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
