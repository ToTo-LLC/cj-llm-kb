"""Tests for POST /api/upload — Plan 08 Task 1.

The upload endpoint accepts a multipart ``file`` field from the browser,
decodes the bytes as UTF-8, and feeds the text to the in-process
``brain_ingest`` tool handler. Four slices:

1. Happy path: text/markdown file → 200 with a ``patch_id`` in the envelope.
2. Missing ``X-Brain-Token`` → 403 (auth required on writes).
3. Cross-origin → 403 (middleware + endpoint).
4. Wrong content-type (application/pdf) → 415 ``unsupported_media_type``.

The happy path queues three FakeLLM responses (classify, summarize, integrate)
— the same pattern ``test_tool_endpoints.py::test_brain_ingest`` uses — so we
exercise the full pipeline without a live LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import PatchSet
from fastapi import FastAPI
from fastapi.testclient import TestClient

_LOOPBACK_ORIGIN = "http://localhost:4317"
_EVIL_ORIGIN = "http://evil.example"


def _seed_vault_for_ingest(vault: Path) -> None:
    """Write the minimum vault layout ingest + archive writers expect."""
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True, exist_ok=True)
    log = vault / "research" / "log.md"
    if not log.exists():
        log.write_text("# research — log\n", encoding="utf-8", newline="\n")
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True, exist_ok=True)
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")


@pytest.fixture
def upload_app(tmp_path: Path) -> FastAPI:
    """App whose vault has the full ingest-ready layout."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    _seed_vault_for_ingest(vault)
    return create_app(vault_root=vault, allowed_domains=("research",))


def _queue_ingest_responses(app: FastAPI) -> None:
    """Queue classify → summarize → integrate JSONs on the FakeLLM.

    Mirrors ``test_tool_endpoints.py::test_brain_ingest`` so the pipeline
    sees a valid response for each call in order.
    """
    llm = app.state.ctx.tool_ctx.llm
    llm.queue('{"source_type": "text", "domain": "research", "confidence": 0.9}')
    llm.queue(
        SummarizeOutput(
            title="Uploaded",
            summary="An uploaded source.",
            key_points=["point"],
            entities=[],
            concepts=["x"],
            open_questions=[],
        ).model_dump_json()
    )
    llm.queue(
        PatchSet(
            new_files=[],
            log_entry="## ingest | Uploaded",
            reason="upload",
        ).model_dump_json()
    )


def test_upload_markdown_happy_path_returns_patch_id(upload_app: FastAPI) -> None:
    """text/markdown upload → 200 with ``patch_id`` in the envelope."""
    with TestClient(upload_app, base_url="http://localhost") as client:
        token = upload_app.state.ctx.token
        assert token is not None
        _queue_ingest_responses(upload_app)

        r = client.post(
            "/api/upload",
            headers={
                "Origin": _LOOPBACK_ORIGIN,
                "X-Brain-Token": token,
            },
            files={
                "file": (
                    "note.md",
                    b"# hello\n\nsome body content",
                    "text/markdown",
                ),
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "patch_id" in body
        assert body["patch_id"]


def test_upload_missing_token_is_rejected(upload_app: FastAPI) -> None:
    """No ``X-Brain-Token`` → 403 ``refused`` (same dependency as every write)."""
    with TestClient(upload_app, base_url="http://localhost") as client:
        r = client.post(
            "/api/upload",
            headers={"Origin": _LOOPBACK_ORIGIN},
            files={
                "file": (
                    "note.md",
                    b"# hello",
                    "text/markdown",
                ),
            },
        )
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["error"] == "refused"


def test_upload_cross_origin_is_rejected(upload_app: FastAPI) -> None:
    """Cross-origin POST → 403 ``refused`` (middleware short-circuit)."""
    with TestClient(upload_app, base_url="http://localhost") as client:
        token = upload_app.state.ctx.token
        assert token is not None

        r = client.post(
            "/api/upload",
            headers={
                "Origin": _EVIL_ORIGIN,
                "X-Brain-Token": token,
            },
            files={
                "file": (
                    "note.md",
                    b"# hello",
                    "text/markdown",
                ),
            },
        )
        assert r.status_code == 403, r.text


def test_upload_pdf_content_type_is_415(upload_app: FastAPI) -> None:
    """application/pdf → 415 ``unsupported_media_type`` (text-only for day one)."""
    with TestClient(upload_app, base_url="http://localhost") as client:
        token = upload_app.state.ctx.token
        assert token is not None

        r = client.post(
            "/api/upload",
            headers={
                "Origin": _LOOPBACK_ORIGIN,
                "X-Brain-Token": token,
            },
            files={
                "file": (
                    "document.pdf",
                    b"%PDF-1.4 binary junk ...",
                    "application/pdf",
                ),
            },
        )
        assert r.status_code == 415, r.text
        body = r.json()
        assert body["error"] == "unsupported_media_type"
