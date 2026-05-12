"""Plan 22 T10 — brain_api integration tests for the watched-folders tools.

The unit pins in :mod:`brain_core.tests.tools.test_watch_folder` /
``test_unwatch_folder`` / ``test_list_watched_folders`` cover the
handlers in isolation. ``test_app_watcher_lifespan`` (T7) pins the
lifespan-to-watcher seam. This file pins the **transport** seam: a
real FastAPI :class:`fastapi.testclient.TestClient` POSTs against the
``/api/tools/<name>`` dispatcher with a lifespan-minted token and the
loopback ``Origin``, the dispatcher runs the registered handler
against the embedded :class:`brain_core.tools.base.ToolContext`, and
the live :class:`Config` on ``app.state.ctx.tool_ctx.config`` mutates
in place so subsequent calls see the new ``watched_folders`` row.

**Plan 22 T10.5 update**: the initial-sync test now also pins that
each per-item ingested source note carries ``source_path`` +
``watched_folder_id`` frontmatter — proves the
``BulkImporter.apply(watched_folder_id=...)`` kwarg threading lands
through end-to-end from the API transport.

Four scenarios:

* **api_watch_folder** — POST ``brain_watch_folder`` with
  ``initial_sync=False`` → 200, ``status="watched"``, the new folder
  appears on ``Config.watched_folders`` AND in
  ``brain_list_watched_folders`` on the next call.
* **api_list_watched** — POST ``brain_list_watched_folders`` returns
  the data shape with a ``folders[]`` array; the rows reflect
  whatever was registered via the watch endpoint.
* **api_initial_sync** — POST ``brain_watch_folder`` with
  ``initial_sync=True`` against a folder pre-seeded with 2 files;
  every queued FakeLLM response is consumed by the
  :class:`BulkImporter`, the data envelope reports both files as
  applied, AND the persisted Config picked up the new folder.
* **api_unwatch** — POST ``brain_unwatch_folder`` after a successful
  watch → status flips to ``unwatched``; the row is removed from
  ``Config.watched_folders``.

The fixture sets up a vault with a writable ``.brain/config.json``
containing the ``research`` domain (the watch tool's cross-field
pre-check rejects orphan domains per Plan 16 T36) and uses
``mount_static_ui=False`` so the catch-all SPA mount doesn't shadow
the API routes.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from brain_api import create_app
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import PatchSet
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ApiClient:
    """Thin wrapper that auto-attaches Origin + X-Brain-Token on every POST.

    Mirrors :class:`brain_api.tests.test_tool_endpoints.ApiClient` so the
    request shape is identical between the per-tool happy-path sweep and
    this watched-folders integration file.
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


def _write_config(brain_dir: Path) -> None:
    """Write a minimal config.json with the ``research`` domain configured.

    The watch tool's cross-field pre-check (per Plan 16 T36) refuses a
    ``WatchedFolder`` whose domain is not in ``Config.domains``. We
    seed both ``research`` and ``personal`` so the seed matches the
    canonical 3-domain layout (``personal`` is the last-resort
    fallback for the lazy-classify path).
    """
    brain_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "domains": ["research", "personal"],
        "active_domain": "research",
        "watched_folders": [],
    }
    (brain_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")


def _seed_vault(vault: Path) -> None:
    """Plant the minimum vault layout the lifespan + tools need.

    ``research/`` with the standard subdirs is enough for both the
    ``brain_list_domains`` smoke probe and the BulkImporter's plan
    walk during initial sync. ``raw/`` subdirs let TextHandler write
    its archive copy without ``mkdir(parents=True)`` exceptions
    (the pipeline DOES create archive dirs lazily, but the explicit
    seed keeps the integration test's setup readable).
    """
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True, exist_ok=True)
    (vault / "research" / "index.md").write_text(
        "# research\n", encoding="utf-8", newline="\n"
    )
    (vault / "research" / "log.md").write_text(
        "# research — log\n", encoding="utf-8", newline="\n"
    )
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True, exist_ok=True)
    (vault / "BRAIN.md").write_text(
        "# BRAIN\n", encoding="utf-8", newline="\n"
    )


@pytest.fixture
def watched_vault(tmp_path: Path) -> Path:
    """A vault wired with a writable config.json + the standard layout."""
    vault = tmp_path / "vault"
    _seed_vault(vault)
    _write_config(vault / ".brain")
    return vault


@pytest.fixture
def watched_app(
    watched_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> FastAPI:
    """A FastAPI app bound to ``watched_vault`` with the SPA mount off.

    ``mount_static_ui=False`` keeps the catch-all from shadowing the
    ``/api/tools/<name>`` routes (the same gotcha the per-tool sweep
    in :mod:`test_tool_endpoints` documents). ``ANTHROPIC_API_KEY``
    is cleared so the lifespan boots with :class:`FakeLLMProvider`
    rather than reaching for a real Anthropic client.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return create_app(
        vault_root=watched_vault,
        allowed_domains=("research",),
        mount_static_ui=False,
    )


@pytest.fixture
def api(watched_app: FastAPI) -> Iterator[ApiClient]:
    """Lifespan-active :class:`ApiClient` bound to ``watched_app``.

    Entering the TestClient context runs the lifespan, which mints
    the app secret and stashes it on ``app.state.ctx.token``. Reading
    the token outside the ``with`` block would see ``None``.
    """
    with TestClient(watched_app, base_url="http://localhost") as base:
        token = watched_app.state.ctx.token
        assert token is not None, "lifespan must mint a token"
        yield ApiClient(base, token=token)


# ---------------------------------------------------------------------------
# (1) api_watch_folder — POST registers a folder + initial_sync=False
# ---------------------------------------------------------------------------


def test_api_watch_folder_registers_folder(
    api: ApiClient, watched_app: FastAPI, tmp_path: Path
) -> None:
    """POST brain_watch_folder → 200, watcher row appears on live Config.

    ``initial_sync=False`` keeps this test focused on the registration
    seam: no LLM responses queued, no BulkImporter call. The data
    envelope must report ``status="watched"`` and the Config in
    memory must show the new ``WatchedFolder``.
    """
    folder = tmp_path / "to_watch"
    folder.mkdir()

    r = api.call(
        "brain_watch_folder",
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
    )
    assert r.status_code == 200, r.text
    envelope = r.json()
    assert set(envelope.keys()) == {"text", "data"}
    data = envelope["data"]
    assert data["status"] == "watched"
    assert data["folder"] == str(folder)
    assert data["domain"] == "research"
    assert data["initial_sync_summary"] is None
    assert data["cost_estimate"] is None

    # Live Config picked up the row in place.
    cfg = watched_app.state.ctx.tool_ctx.config
    assert any(wf.path == str(folder) for wf in cfg.watched_folders), (
        f"watched_folders did not include the new row: {cfg.watched_folders!r}"
    )

    # Persisted to disk under .brain/config.json — proves the persist
    # path round-tripped, not just an in-memory mutation.
    on_disk = json.loads(
        (watched_app.state.vault_root / ".brain" / "config.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(wf["path"] == str(folder) for wf in on_disk["watched_folders"])


# ---------------------------------------------------------------------------
# (2) api_list_watched — POST returns count + folders[] reflecting state
# ---------------------------------------------------------------------------


def test_api_list_watched_reflects_registered_folders(
    api: ApiClient, tmp_path: Path
) -> None:
    """brain_list_watched_folders returns the rows added via brain_watch_folder.

    Pins the read-after-write contract end-to-end: the same Config
    instance that brain_watch_folder mutated in step (1) is what
    brain_list_watched_folders reads from. A bug that copied the
    config (rather than referencing it) would surface here as a
    stale empty list.
    """
    # Pre: list with no folders registered.
    r = api.call("brain_list_watched_folders")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["folders"] == []

    # Register one folder.
    folder = tmp_path / "list_me"
    folder.mkdir()
    api.call(
        "brain_watch_folder",
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
    )

    # Post: list now reflects the registration.
    r = api.call("brain_list_watched_folders")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["folders"]) == 1
    row = data["folders"][0]
    assert row["path"] == str(folder)
    assert row["domain"] == "research"
    # ``enabled`` default is True per the schema.
    assert row["enabled"] is True
    # The runtime-stat join surfaces 0/0 for a freshly-registered
    # folder (no files imported yet because initial_sync=False above).
    assert row["file_count"] == 0
    assert row["orphan_count"] == 0


# ---------------------------------------------------------------------------
# (3) api_initial_sync — brain_watch_folder with initial_sync=True ingests
# ---------------------------------------------------------------------------


def test_api_watch_folder_initial_sync_imports_files(
    api: ApiClient, watched_app: FastAPI, tmp_path: Path
) -> None:
    """initial_sync=True drives BulkImporter end-to-end via the API.

    Seeds 2 ``.txt`` files in the folder, queues 2 sets of (summarize +
    integrate) responses on the FakeLLM (BulkImporter passes
    ``domain_override`` per ``WatchedFolder.domain`` so classify is
    skipped — same path as the watcher-triggered ingest). On a
    successful sync the data envelope reports both files as applied
    AND the vault has 2 freshly-written source notes.
    """
    folder = tmp_path / "sync_me"
    folder.mkdir()
    (folder / "alpha.txt").write_text(
        "Alpha content for the initial sync.\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "beta.txt").write_text(
        "Beta content for the initial sync.\n",
        encoding="utf-8",
        newline="\n",
    )

    fake = watched_app.state.ctx.tool_ctx.llm
    # 2 files × 2 calls each (summarize + integrate). Classify is
    # skipped because BulkImporter forwards ``domain_override`` to
    # the pipeline when the watch was created with a domain.
    for slug in ("alpha", "beta"):
        fake.queue(
            SummarizeOutput(
                title=slug,
                summary=f"summary of {slug}",
                key_points=[f"{slug} point"],
                entities=[],
                concepts=[],
                open_questions=[],
            ).model_dump_json()
        )
        fake.queue(
            PatchSet(
                new_files=[],
                edits=[],
                index_entries=[],
                log_entry=f"## ingest | source | [[{slug}]]",
                reason="initial sync",
            ).model_dump_json()
        )

    r = api.call(
        "brain_watch_folder",
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "watched"
    assert data["initial_sync_summary"] is not None
    summary = data["initial_sync_summary"]
    assert summary["planned"] == 2
    assert summary["applied"] == 2
    assert summary["failed"] == 0
    # cost_estimate is populated when initial_sync=True (D3 — informational).
    cost_est = data["cost_estimate"]
    assert cost_est is not None
    assert cost_est["file_count"] == 2
    assert cost_est["estimated_tokens"] > 0

    # And the vault picked up both notes.
    sources_dir = watched_app.state.vault_root / "research" / "sources"
    notes = list(sources_dir.glob("*.md"))
    assert len(notes) == 2, (
        f"expected 2 source notes after initial sync, got: {notes!r}"
    )
    titles = {note.stem for note in notes}
    assert titles == {"alpha", "beta"}

    # Plan 22 T10.5: each note must carry the watched-context
    # frontmatter so the T6 :class:`WatchedFolderWatcher` can map
    # subsequent modify/delete events back to the right vault note.
    # Pre-T10.5 the initial-sync path silently dropped these fields,
    # so subsequent watcher events on the imported files would have
    # produced duplicate notes (modify) or silently no-opped (delete).
    from brain_core.vault.frontmatter import parse_frontmatter

    recorded_source_paths = set()
    for note_path in notes:
        fm, _body = parse_frontmatter(note_path.read_text(encoding="utf-8"))
        assert fm["watched_folder_id"] == str(folder), (
            f"note {note_path.name} missing watched_folder_id: {fm!r}"
        )
        assert fm["source_path"] is not None, (
            f"note {note_path.name} missing source_path: {fm!r}"
        )
        recorded_source_paths.add(fm["source_path"])
    expected_source_paths = {
        str((folder / "alpha.txt").resolve()),
        str((folder / "beta.txt").resolve()),
    }
    assert recorded_source_paths == expected_source_paths, (
        f"per-item source_path threading wrong: got {recorded_source_paths!r}, "
        f"expected {expected_source_paths!r}"
    )


# ---------------------------------------------------------------------------
# (4) api_unwatch — POST removes the registered folder
# ---------------------------------------------------------------------------


def test_api_unwatch_folder_removes_row(
    api: ApiClient, watched_app: FastAPI, tmp_path: Path
) -> None:
    """brain_unwatch_folder removes the row from Config.watched_folders.

    Round-trip: watch a folder, then unwatch it. The data envelope
    must flip to ``status="unwatched"`` and the live Config must
    NOT contain the row afterwards. A residual row would cause the
    next lifespan boot to re-schedule a watcher on a path the user
    explicitly removed.
    """
    folder = tmp_path / "stop_watching"
    folder.mkdir()

    # Step 1: register.
    r = api.call(
        "brain_watch_folder",
        {
            "folder": str(folder),
            "domain": "research",
            "initial_sync": False,
        },
    )
    assert r.status_code == 200, r.text
    cfg = watched_app.state.ctx.tool_ctx.config
    assert any(wf.path == str(folder) for wf in cfg.watched_folders)

    # Step 2: unwatch.
    r = api.call("brain_unwatch_folder", {"folder": str(folder)})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "unwatched"
    assert data["folder"] == str(folder)

    # Step 3: Config no longer carries the row.
    cfg = watched_app.state.ctx.tool_ctx.config
    assert all(wf.path != str(folder) for wf in cfg.watched_folders), (
        f"unwatch did not remove the row: {cfg.watched_folders!r}"
    )

    # And the disk reflects the removal — proves the persist path
    # round-tripped through the unwatch tool, not just an in-memory
    # mutation.
    on_disk = json.loads(
        (watched_app.state.vault_root / ".brain" / "config.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(
        wf["path"] != str(folder) for wf in on_disk["watched_folders"]
    )
