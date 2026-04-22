"""POST /api/upload — Plan 08 Task 1.

Accept a multipart ``file`` field from the browser, decode the bytes as UTF-8,
stage the content as a temp file inside the vault's ``raw/inbox/`` subtree,
and feed the path to the in-process ``brain_ingest`` tool handler. The static
export of the SPA drops the Next.js multipart proxy that used to live at
``/api/proxy/upload``; brain_api now owns the full flow.

Why a temp file rather than raw text? The ingest pipeline's dispatcher
(:mod:`brain_core.ingest.dispatcher`) routes by file extension + existence;
``TextHandler`` accepts only ``Path`` inputs with a ``.txt/.md/.markdown``
suffix. Writing the upload to a temp file inside the vault (mirroring the
existing bulk-importer flow) lets the pipeline take its normal path + archive
the source alongside the staged PatchSet.

Policy:
- Content-type whitelist: ``text/plain``, ``text/markdown``, ``text/x-markdown``,
  ``application/json``. Anything else → 415 ``unsupported_media_type``.
- Size cap: 10 MiB. Larger → 413 ``file_too_large``. This keeps an accidental
  multi-gigabyte upload (e.g. a CSV dragged in by mistake) from consuming the
  whole process's memory before we even get to the ingest pipeline.
- UTF-8 decode failure → 400 ``invalid_input``. The day-one ingest pipeline
  expects text; binary would need a different handler.
- ``X-Brain-Token`` required; shared :func:`brain_api.auth.require_token`
  dependency does the constant-time compare.

Returns ``{patch_id: str}`` on 200. Other statuses reuse the flat error
envelope ``{"error", "message", "detail"}`` via the global handler.
"""

from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from brain_api.auth import enforce_json_accept, require_token
from brain_api.context import AppContext, get_ctx
from brain_api.endpoints._origin import require_loopback_origin
from brain_api.errors import ApiError

router = APIRouter(tags=["upload"])

# Text-only for Plan 08. PDF + binary deferred to Plan 09 (per plan scope).
_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/json",
    }
)

# 10 MiB. Picked to match the soft ceiling in the frontend's drag-and-drop
# affordance (same plan, Task 2). Anything above this is almost certainly the
# wrong file type in disguise (CSV export, sqlite dump, etc.).
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


_CONTENT_TYPE_SUFFIX: dict[str, str] = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "application/json": ".json",
}


def _suffix_for_content_type(content_type: str, filename: str | None) -> str:
    """Choose a safe on-disk suffix for the staged file.

    Prefer the content-type mapping (authoritative per the whitelist) over
    the upload-supplied filename, which can lie or be missing. We fall back
    to ``.txt`` if the content-type is somehow outside the whitelist — this
    path is defensive; the content-type check above already rejects any
    non-whitelisted type with a 415.
    """
    mapped = _CONTENT_TYPE_SUFFIX.get(content_type)
    if mapped is not None:
        return mapped
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in {".txt", ".md", ".markdown", ".json"}:
            return suffix
    return ".txt"


class UploadResponse(BaseModel):
    """Typed 200 body — a single patch_id the browser polls on."""

    patch_id: str


@router.post(
    "/api/upload",
    response_model=UploadResponse,
    dependencies=[
        Depends(require_loopback_origin),
        Depends(enforce_json_accept),
        Depends(require_token),
    ],
    summary="Upload a text file for ingest; returns a staged patch_id.",
)
async def upload_file(
    file: UploadFile = File(...),  # noqa: B008 — FastAPI File(...) idiom
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI Depends idiom
) -> UploadResponse:
    """Decode ``file`` as UTF-8 text and dispatch to ``brain_ingest``."""
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ApiError(
            status=415,
            code="unsupported_media_type",
            message=(
                "only text uploads are supported today "
                "(text/plain, text/markdown, text/x-markdown, application/json)"
            ),
            detail={"received": content_type or "application/octet-stream"},
        )

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise ApiError(
            status=413,
            code="file_too_large",
            message=f"upload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MiB cap",
            detail={"size_bytes": len(raw), "limit_bytes": _MAX_UPLOAD_BYTES},
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ApiError(
            status=400,
            code="invalid_input",
            message="upload is not valid UTF-8 text",
            detail={"decode_error": str(exc)},
        ) from exc

    # Stage the upload inside ``<vault>/raw/inbox/<timestamp>-<rand>-<name>``
    # so ``TextHandler`` (path-based) claims it. The pipeline itself writes a
    # copy into ``raw/archive/`` on success; the inbox copy stays put as the
    # authoritative source record (same convention ``brain_bulk_import``
    # uses). Filename is sanitized to the original suffix only — upload-
    # supplied names never reach the vault directly.
    suffix = _suffix_for_content_type(content_type, file.filename)
    inbox = ctx.vault_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stem = f"{int(time.time())}-{secrets.token_hex(4)}"
    staged = inbox / f"{stem}{suffix}"
    staged.write_text(text, encoding="utf-8", newline="\n")

    # Dispatch via the in-process tool registry so the ingest tool sees
    # exactly the same ``ToolContext`` the tool-dispatcher endpoint would
    # hand it. No HTTP round-trip, no JSON serialization — direct call.
    module = ctx.tool_by_name.get("brain_ingest")
    if module is None:  # pragma: no cover — registry wiring failure at boot
        raise ApiError(
            status=500,
            code="internal",
            message="brain_ingest tool is not registered",
        )

    result = await module.handle({"source": str(staged)}, ctx.tool_ctx)
    data: dict[str, Any] = result.data or {}
    patch_id = data.get("patch_id")
    if not isinstance(patch_id, str) or not patch_id:
        # Non-OK ingest (classify failed, domain rejected, etc.) surfaces with
        # no patch_id. Mirror the underlying status in a 400 rather than a
        # generic 500 — the client has a choice to retry / change the file.
        raise ApiError(
            status=400,
            code="ingest_failed",
            message=f"ingest did not stage a patch: {data.get('status', 'unknown')}",
            detail=data,
        )
    return UploadResponse(patch_id=patch_id)
