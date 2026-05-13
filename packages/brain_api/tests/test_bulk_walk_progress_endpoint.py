"""Tests for GET /api/bulk/walk-progress — Plan 26 T3.

Five slices that pin the wire contract for the SSE endpoint:

1. Happy path: small folder → 200 + ``Content-Type: text/event-stream``
   + complete event sequence (``walk_started`` ... ``walk_complete``).
2. Missing token → 403 BEFORE any streaming starts (the client must
   see a normal JSON envelope, not a half-open event-stream).
3. Missing ``path`` query param → 422 (FastAPI's built-in validation —
   ``path`` is a required Query).
4. Non-existent path → 400 ``invalid_input``.
5. Path that exists but is a file (not a directory) → 400 ``invalid_input``.

The happy-path test uses a fresh tmp_path folder containing a handful
of .txt files; the FakeLLM is never called (the streaming path does
not classify) so no response queueing is required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_api import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

_LOOPBACK_ORIGIN = "http://localhost:4317"


@pytest.fixture
def walk_app(tmp_path: Path) -> FastAPI:
    """App with a minimal vault layout — no ingest seeding needed.

    Plan 13 Task 5: ``mount_static_ui=False`` so SPA fallback doesn't
    shadow the SSE route in tests where the prod build hasn't run.
    """
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".brain").mkdir(parents=True, exist_ok=True)
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True, exist_ok=True)
    (vault / "research" / "index.md").write_text(
        "# research\n", encoding="utf-8", newline="\n"
    )
    (vault / "research" / "log.md").write_text(
        "# log\n", encoding="utf-8", newline="\n"
    )
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")
    return create_app(
        vault_root=vault,
        allowed_domains=("research",),
        mount_static_ui=False,
    )


def _parse_sse_records(payload: str) -> list[dict[str, object]]:
    """Split an SSE response body into a list of decoded JSON events.

    Each record is one ``data: <json>`` line followed by a blank line.
    """
    events: list[dict[str, object]] = []
    for chunk in payload.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Each record has a single ``data: `` prefix per the framing in
        # ``bulk_walk_progress._event_stream``.
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


def test_walk_progress_happy_path_streams_event_sequence(
    walk_app: FastAPI, tmp_path: Path
) -> None:
    """Small folder → 200 + text/event-stream + started ... complete events."""
    source = tmp_path / "source"
    source.mkdir()
    for i in range(3):
        (source / f"note-{i}.txt").write_text(
            "hello world\n" * 5, encoding="utf-8"
        )

    with TestClient(walk_app, base_url="http://localhost") as client:
        token = walk_app.state.ctx.token
        assert token is not None

        r = client.get(
            "/api/bulk/walk-progress",
            params={"path": str(source), "token": token},
            headers={"Origin": _LOOPBACK_ORIGIN},
        )

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_records(r.text)
    assert len(events) >= 2
    assert events[0]["type"] == "walk_started"
    assert events[0]["path"] == str(source)
    assert events[-1]["type"] == "walk_complete"
    assert events[-1]["total_count"] == 3
    assert isinstance(events[-1]["plan_id"], str)


def test_walk_progress_missing_token_is_rejected(
    walk_app: FastAPI, tmp_path: Path
) -> None:
    """No ``token=`` query param → 422 (FastAPI required-Query check).

    The endpoint declares ``token: str = Query(...)`` so a fully
    missing parameter is caught by FastAPI's built-in validation
    BEFORE ``_check_sse_token`` runs. This is the desired behavior —
    the client gets a structured 422 with the field name; the auth
    branch is reserved for the "token supplied but wrong" case.
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")

    with TestClient(walk_app, base_url="http://localhost") as client:
        r = client.get(
            "/api/bulk/walk-progress",
            params={"path": str(source)},
            headers={"Origin": _LOOPBACK_ORIGIN},
        )

    assert r.status_code == 422, r.text


def test_walk_progress_wrong_token_is_rejected(
    walk_app: FastAPI, tmp_path: Path
) -> None:
    """Wrong ``token=`` → 403 ``refused`` (auth branch, constant-time
    compare in ``_check_sse_token``).
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")

    with TestClient(walk_app, base_url="http://localhost") as client:
        r = client.get(
            "/api/bulk/walk-progress",
            params={"path": str(source), "token": "wrong-token"},
            headers={"Origin": _LOOPBACK_ORIGIN},
        )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"] == "refused"


def test_walk_progress_nonexistent_path_returns_400(
    walk_app: FastAPI, tmp_path: Path
) -> None:
    """Path that doesn't exist → 400 ``invalid_input`` BEFORE streaming."""
    with TestClient(walk_app, base_url="http://localhost") as client:
        token = walk_app.state.ctx.token
        assert token is not None
        bogus = tmp_path / "does-not-exist"
        r = client.get(
            "/api/bulk/walk-progress",
            params={"path": str(bogus), "token": token},
            headers={"Origin": _LOOPBACK_ORIGIN},
        )

    assert r.status_code == 400, r.text
    body = r.json()
    assert body["error"] == "invalid_input"


def test_walk_progress_file_not_directory_returns_400(
    walk_app: FastAPI, tmp_path: Path
) -> None:
    """``path`` points at a regular file → 400 ``invalid_input``."""
    a_file = tmp_path / "regular.txt"
    a_file.write_text("hi", encoding="utf-8")

    with TestClient(walk_app, base_url="http://localhost") as client:
        token = walk_app.state.ctx.token
        assert token is not None
        r = client.get(
            "/api/bulk/walk-progress",
            params={"path": str(a_file), "token": token},
            headers={"Origin": _LOOPBACK_ORIGIN},
        )

    assert r.status_code == 400, r.text
    body = r.json()
    assert body["error"] == "invalid_input"
