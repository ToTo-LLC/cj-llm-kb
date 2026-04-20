"""Per-tool REST endpoint tests — 18 tools, happy + reject paths.

Task 13 closes Group 4. Every tool registered in ``brain_core.tools`` has a
curl-driveable integration test here: the tests hit the real
``POST /api/tools/<name>`` dispatcher through FastAPI's ``TestClient`` with a
real ``Origin`` header and the lifespan-minted ``X-Brain-Token``. The only
boundary they mock is the network -- ``FakeLLMProvider`` replays queued JSON
responses in FIFO order so the ingest / classify / bulk_import pipelines stay
deterministic.

Fixture shape parity with ``packages/brain_mcp/tests/test_tool_*.py`` is
intentional: the handlers are identical (brain_core owns them); only the
shim differs (MCP vs HTTP). Where the ingest/bulk_import pipelines need the
full vault layout (``raw/inbox/``, ``research/sources/``, etc.) we augment the
seeded vault in-place -- the ``app`` fixture already bound ``vault_root`` to
it at lifespan, so mutations after construction are visible to handlers.

Task 15 installed :func:`brain_api.errors.register_error_handlers`, which
turns unhandled ``ScopeError`` into 403 ``scope`` and ``KeyError`` into 404
``not_found``. The reject-path tests below pin that mapping; the paired
``*_currently_500`` tests (pre-Task-15 pins) have been deleted.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import PatchSet
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared helper + fixture
# ---------------------------------------------------------------------------


class ApiClient:
    """TestClient wrapper that auto-attaches Origin + X-Brain-Token on every POST.

    Keeps per-test boilerplate to a single ``api.call(name, body)`` line. The
    ``Origin: http://localhost:4317`` default matches Task 8's allowlist; the
    ``base_url="http://localhost"`` on the wrapped TestClient keeps the
    ``Host`` header on the loopback allowlist too (else the middleware would
    reject ``Host: testserver``).
    """

    def __init__(
        self,
        base: TestClient,
        token: str,
        origin: str = "http://localhost:4317",
    ) -> None:
        self._base = base
        self._headers = {"Origin": origin, "X-Brain-Token": token}

    def call(self, name: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self._base.post(
            f"/api/tools/{name}",
            json=body or {},
            headers=self._headers,
        )


@pytest.fixture
def api(app: FastAPI):
    """Lifespan-active ApiClient.

    Entering ``TestClient(app, ...)`` as a context manager runs FastAPI's
    lifespan, which is where the app-secret token is minted and stashed on
    ``app.state.ctx.token``. Reading the token outside the ``with`` block
    would see ``None``.
    """
    with TestClient(app, base_url="http://localhost") as base:
        token = app.state.ctx.token
        assert token is not None, "lifespan must mint a token"
        yield ApiClient(base, token=token)


def _augment_vault_for_ingest(vault: Path) -> None:
    """Add the subdirs the ingest pipeline + BulkImporter expect.

    ``seeded_vault`` in ``conftest.py`` is read-friendly (notes + index +
    BRAIN.md) but lacks the ``research/{sources,entities,concepts,synthesis}``
    / ``research/log.md`` / ``raw/{inbox,failed,archive}`` layout the ingest
    pipeline writes into. Tests that invoke ``brain_ingest`` or
    ``brain_bulk_import`` call this helper first so VaultWriter + archive_dir
    + failure recorder all find their target directories.
    """
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True, exist_ok=True)
    log = vault / "research" / "log.md"
    if not log.exists():
        log.write_text("# research — log\n", encoding="utf-8", newline="\n")
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Happy-path parametrized sweep — 10 tools that need no fixture setup.
# ---------------------------------------------------------------------------


# Each tuple: (name, body, assertion over envelope["data"]).
_HAPPY_CASES: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], bool]]] = [
    ("brain_list_domains", {}, lambda d: "research" in d["domains"]),
    ("brain_get_index", {}, lambda d: "body" in d),
    (
        "brain_read_note",
        {"path": "research/notes/karpathy.md"},
        lambda d: "body" in d,
    ),
    ("brain_search", {"query": "karpathy"}, lambda d: isinstance(d["hits"], list)),
    ("brain_recent", {}, lambda d: "notes" in d and "limit_used" in d),
    ("brain_get_brain_md", {}, lambda d: "You are brain" in d["body"]),
    ("brain_list_pending_patches", {}, lambda d: d["count"] == 0),
    ("brain_cost_report", {}, lambda d: "today_usd" in d),
    ("brain_lint", {}, lambda d: d["status"] == "not_implemented"),
    (
        "brain_undo_last",
        {},
        lambda d: d["status"] in ("reverted", "nothing_to_undo"),
    ),
]


@pytest.mark.parametrize("name,body,assertion", _HAPPY_CASES)
def test_happy_path(
    api: ApiClient,
    name: str,
    body: dict[str, Any],
    assertion: Callable[[dict[str, Any]], bool],
) -> None:
    """Every happy-path tool returns 200 + the pinned ``ToolResponse`` envelope.

    The envelope must contain exactly ``{"text", "data"}`` — Task 12's
    ``response_model=ToolResponse`` drops any extra keys handlers might emit,
    so this assertion pins the wire contract. The per-tool ``assertion``
    lambda spot-checks a meaningful payload field (beyond "not empty") so a
    regression to an empty dict can't silently pass.
    """
    response = api.call(name, body)
    assert response.status_code == 200, response.text
    envelope = response.json()
    assert set(envelope.keys()) == {"text", "data"}
    assert assertion(envelope["data"]), f"assertion failed for {name}: {envelope['data']!r}"


# ---------------------------------------------------------------------------
# Hand-written happy-path tests for tools that need fixture setup.
# ---------------------------------------------------------------------------


def test_brain_propose_note(api: ApiClient) -> None:
    """Staging a new-note patch returns a patch_id; vault stays untouched."""
    response = api.call(
        "brain_propose_note",
        {
            "path": "research/notes/new-idea.md",
            "content": "# new idea\n\nbody",
            "reason": "captured via REST",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "patch_id" in data
    assert data["patch_id"]  # non-empty string


def test_brain_apply_patch(api: ApiClient, app: FastAPI, seeded_vault: Path) -> None:
    """propose → apply round-trip writes the file on disk.

    Goes through the REST layer end-to-end (rather than reaching into
    ``pending_store`` directly) so the test exercises the same path Claude
    Desktop / the browser will take.
    """
    target = "research/notes/apply-me.md"
    r = api.call(
        "brain_propose_note",
        {
            "path": target,
            "content": "# apply me",
            "reason": "demo",
        },
    )
    assert r.status_code == 200, r.text
    patch_id = r.json()["data"]["patch_id"]

    r = api.call("brain_apply_patch", {"patch_id": patch_id})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "applied"
    assert "undo_id" in data
    assert (seeded_vault / "research" / "notes" / "apply-me.md").exists()


def test_brain_reject_patch(api: ApiClient) -> None:
    """propose → reject flips the envelope to ``rejected``; vault never touched."""
    r = api.call(
        "brain_propose_note",
        {
            "path": "research/notes/reject-me.md",
            "content": "# reject me",
            "reason": "demo",
        },
    )
    assert r.status_code == 200, r.text
    patch_id = r.json()["data"]["patch_id"]

    r = api.call("brain_reject_patch", {"patch_id": patch_id, "reason": "not useful"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "rejected"


def test_brain_classify(api: ApiClient, app: FastAPI) -> None:
    """brain_classify passes content to a queued FakeLLM response."""
    # The ClassifyOutput schema requires source_type + domain + confidence;
    # include ``reason`` so the envelope is informative even though the
    # schema tolerates its absence.
    app.state.ctx.tool_ctx.llm.queue(
        '{"source_type": "text", "domain": "research", "confidence": 0.9}'
    )

    r = api.call("brain_classify", {"content": "Karpathy on LLMs"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["domain"] == "research"
    assert data["confidence"] == 0.9


def test_brain_bulk_import(api: ApiClient, app: FastAPI, tmp_path: Path) -> None:
    """Dry-run bulk_import returns ``planned`` with a single-file count.

    The importer's plan() phase runs one classify call per candidate; we
    queue one response for the single ``.txt`` in the source folder. Writing
    the file with ``newline="\\n"`` keeps line endings LF across platforms,
    matching the project's cross-platform rule.
    """
    folder = tmp_path / "inbox-for-bulk"
    folder.mkdir()
    (folder / "a.txt").write_text("hello world", encoding="utf-8", newline="\n")
    app.state.ctx.tool_ctx.llm.queue(
        '{"source_type": "text", "domain": "research", "confidence": 0.9}'
    )

    r = api.call("brain_bulk_import", {"folder": str(folder)})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "planned"
    assert data["file_count"] == 1


def test_brain_ingest(api: ApiClient, app: FastAPI, seeded_vault: Path, tmp_path: Path) -> None:
    """Single-file ingest stages a PatchSet (``status=pending``) without writing.

    The pipeline makes three LLM calls per run (classify, summarize,
    integrate) — we queue one JSON response per call in order. We augment the
    seeded vault with the ``research/{sources,...}`` + ``raw/`` subdirs that
    the IngestPipeline and failure recorder expect; the ``app`` fixture
    bound ``vault_root`` at lifespan time but the filesystem is shared, so
    these mutations are visible to the handler.

    Using an on-disk .txt file (rather than a raw-text string) keeps the
    test on the same handler path as bulk_import + the MCP integration
    tests — ``TextHandler`` claims ``.txt`` and archives the file into
    ``raw/archive/<domain>/YYYY/MM/``.
    """
    _augment_vault_for_ingest(seeded_vault)
    src = tmp_path / "demo.txt"
    src.write_text(
        "Karpathy wrote about LLM wikis.\n",
        encoding="utf-8",
        newline="\n",
    )

    # classify → summarize → integrate, in that order.
    app.state.ctx.tool_ctx.llm.queue(
        '{"source_type": "text", "domain": "research", "confidence": 0.9}'
    )
    app.state.ctx.tool_ctx.llm.queue(
        SummarizeOutput(
            title="Demo",
            summary="A demo source.",
            key_points=["point"],
            entities=[],
            concepts=["x"],
            open_questions=[],
        ).model_dump_json()
    )
    app.state.ctx.tool_ctx.llm.queue(
        PatchSet(
            new_files=[],
            log_entry="## ingest | Demo",
            reason="demo",
        ).model_dump_json()
    )

    r = api.call("brain_ingest", {"source": str(src)})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "pending"
    assert "patch_id" in data


def test_brain_config_get(api: ApiClient) -> None:
    """brain_config_get returns ``value`` for a whitelisted key."""
    r = api.call("brain_config_get", {"key": "active_domain"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "value" in data


def test_brain_config_set(api: ApiClient) -> None:
    """brain_config_set reports ``persisted=False`` — Plan 07 lands persistence."""
    r = api.call("brain_config_set", {"key": "log_llm_payloads", "value": True})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "updated"
    assert data["persisted"] is False


# ---------------------------------------------------------------------------
# Reject-path spot checks.
#
# Task 15 wired :func:`brain_api.errors.register_error_handlers`, which turns
# unhandled ``ScopeError`` into 403 ``scope`` and unknown-patch ``KeyError``
# into 404 ``not_found``. The flat envelope is ``{"error", "message", "detail"}``
# — no ``detail``-wrap anymore.
# ---------------------------------------------------------------------------


def test_read_note_out_of_scope_is_403(api: ApiClient) -> None:
    """Reading ``personal/`` from a research-scoped app → 403 ``scope``.

    The handler raises :class:`brain_core.vault.paths.ScopeError`; the Task 15
    handler maps it to 403 with ``error == "scope"`` at the top level of the
    response body.
    """
    r = api.call("brain_read_note", {"path": "personal/notes/secret.md"})
    assert r.status_code == 403
    assert r.json()["error"] == "scope"


def test_propose_note_missing_reason_is_400(api: ApiClient) -> None:
    """Task 11 Pydantic validation catches a missing required field → 400.

    ``brain_propose_note`` requires ``path``, ``content``, and ``reason``.
    Sending only the first two must be rejected before the handler runs. Task
    15 lets the :class:`pydantic.ValidationError` bubble; the global handler
    renders the flat ``{"error": "invalid_input", ...}`` envelope with the
    canonical ``errors()`` list under ``detail.errors``.
    """
    r = api.call(
        "brain_propose_note",
        {"path": "research/notes/x.md", "content": "x"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "invalid_input"
    # Pydantic's canonical errors list lives under ``detail.errors`` — that
    # nesting is intentional (structured payload, not a prose message).
    assert isinstance(body["detail"]["errors"], list)
    assert body["detail"]["errors"], "errors list should not be empty"


def test_apply_unknown_patch_is_404(api: ApiClient) -> None:
    """Unknown patch_id → 404 ``not_found``.

    The handler raises ``KeyError(...)`` from the pending-patch store; Task 15
    maps it to 404 with the flat ``{"error": "not_found", ...}`` envelope.
    """
    r = api.call("brain_apply_patch", {"patch_id": "does-not-exist"})
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"
