"""Plan 22 T7 — brain_api lifespan integration for :class:`WatchedFolderWatcher`.

Pins the symmetric-watcher (D7) wiring in :func:`brain_api.app._lifespan`:

1. Startup with empty ``watched_folders``: watcher is instantiated (so the
   hot-reload bridge has something to restart) AND ``start()`` is called
   with no scheduled paths.
2. Startup with non-empty ``watched_folders``: watcher is instantiated
   exactly once, the constructor receives the full list (including the
   disabled entry — filtering happens inside the watcher's ``start()``
   so the row survives an enable-toggle restart), and ``start()`` is
   called once.
3. Shutdown: ``watcher.stop()`` is called before the lifespan exits AND
   before the ``ConfigWatcher.stop()`` (T7 teardown order pin).
4. Disabled-only folder list: the disabled entry is forwarded to the
   watcher unchanged; the watcher's own filter drops it inside
   ``start()`` — verified by the watcher-internals tests in
   ``brain_core/tests/watch/test_folder_watcher.py``. Here we pin the
   contract at the brain_api seam: the lifespan does NOT filter
   ``enabled=False`` on its way in.
5. Hot-reload restart: mid-lifespan, a ``_on_config_change`` callback
   with a modified ``Config.watched_folders`` stops the existing
   watcher AND constructs a fresh one with the new folder list. The
   unchanged-folders case is the negative: a config change that does
   NOT touch ``watched_folders`` must NOT restart the watcher.
6. Monkeypatch-binding regression pin (Plan 17 T17 lesson): patches
   ``brain_api.app.WatchedFolderWatcher`` — the import-bound name in
   the lifespan — and verifies the patch fires. Patching only
   ``brain_core.watch.WatchedFolderWatcher`` would NOT intercept the
   lifespan because :mod:`brain_api.app` re-exports the symbol at
   import time. Tests 1, 2, 5 belt-and-suspenders BOTH names (plain
   ``patch`` on the source binding, no ``raising=False``); Test 6
   patches ONLY the import-bound name as a regression pin — if it
   ever stops firing, the import site moved and the patch targets in
   the rest of the file must be re-audited.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from brain_api.app import _on_config_change, _watched_folders_changed, create_app
from brain_core.config.schema import Config, WatchedFolder
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeWatcher:
    """Records construction args + ``start`` / ``stop`` calls.

    Mirrors the public contract of
    :class:`brain_core.watch.WatchedFolderWatcher` to the extent the
    lifespan touches it: a constructor + ``start()`` + ``stop()``.

    The class-level ``instances`` list is reset by the
    :func:`_reset_fake_watcher_instances` fixture between tests so a
    leak across tests can't pollute assertions.
    """

    instances: list[_FakeWatcher] = []

    def __init__(
        self,
        observers: list[WatchedFolder],
        pipeline: Any,
        *,
        allowed_domains: tuple[str, ...] | None = None,
        **kwargs: Any,
    ) -> None:
        self.observers = list(observers)
        self.pipeline = pipeline
        self.allowed_domains = allowed_domains
        self.kwargs = kwargs
        self.start_called = 0
        self.stop_called = 0
        self._lock = threading.Lock()
        _FakeWatcher.instances.append(self)

    def start(self) -> None:
        with self._lock:
            self.start_called += 1

    def stop(self) -> None:
        with self._lock:
            self.stop_called += 1


@pytest.fixture(autouse=True)
def _reset_fake_watcher_instances() -> Iterator[None]:
    """Drop the cross-test class-level instance list before + after each test."""
    _FakeWatcher.instances = []
    yield
    _FakeWatcher.instances = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_config(
    brain_dir: Path,
    *,
    watched_folders: list[dict[str, Any]] | None = None,
    domains: list[dict[str, Any]] | None = None,
) -> Path:
    """Write the minimal config.json with optional watched_folders + domains.

    The lifespan resolves config via :func:`resolve_config` which honors
    ``cli_overrides["vault_path"]`` — we only need a parsable JSON shape
    on disk for the loader to find it.
    """
    brain_dir.mkdir(parents=True, exist_ok=True)
    config_path = brain_dir / "config.json"
    blob: dict[str, Any] = {}
    if domains is not None:
        blob["domains"] = domains
    if watched_folders is not None:
        blob["watched_folders"] = watched_folders
    config_path.write_text(json.dumps(blob), encoding="utf-8")
    return config_path


def _seed_vault(vault: Path) -> None:
    """Plant a minimal research domain so ``build_app_context`` doesn't fail."""
    (vault / "research").mkdir(parents=True, exist_ok=True)
    (vault / "research" / "index.md").write_text(
        "# research\n", encoding="utf-8", newline="\n"
    )
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")


def _make_watched_folder_dict(path: Path, domain: str, *, enabled: bool = True) -> dict[str, Any]:
    return {
        "path": str(path),
        "domain": domain,
        "enabled": enabled,
        "policy": "overwrite",
        "include_subdirs": True,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault_empty(tmp_path: Path) -> Path:
    """A minimal vault with an empty ``watched_folders`` list."""
    v = tmp_path / "vault"
    _seed_vault(v)
    _write_minimal_config(v / ".brain")
    return v


@pytest.fixture()
def vault_with_folders(tmp_path: Path) -> Path:
    """A vault with two enabled watched folders + one disabled entry."""
    v = tmp_path / "vault"
    _seed_vault(v)
    src1 = tmp_path / "src_one"
    src2 = tmp_path / "src_two"
    src3 = tmp_path / "src_three_disabled"
    for d in (src1, src2, src3):
        d.mkdir(parents=True, exist_ok=True)
    _write_minimal_config(
        v / ".brain",
        watched_folders=[
            _make_watched_folder_dict(src1, "research"),
            _make_watched_folder_dict(src2, "research"),
            _make_watched_folder_dict(src3, "research", enabled=False),
        ],
    )
    return v


# ---------------------------------------------------------------------------
# Test 1: empty watched_folders → watcher instantiated + started, no schedule
# ---------------------------------------------------------------------------


def test_lifespan_starts_watcher_with_empty_watched_folders(
    vault_empty: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty list still instantiates the watcher (for the hot-reload bridge).

    The lifespan must always wire up ``app.state.folder_watcher`` so the
    :func:`_on_config_change` callback has something to restart when a
    user later adds their first ``WatchedFolder`` via Settings — without
    a startup-time instance, the first ``brain_watch_folder`` call
    would have to special-case "create the watcher". Keep that branch
    out of the hot-reload path; always boot the watcher.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(vault_root=vault_empty, allowed_domains=("research",), mount_static_ui=False)

    # Patch BOTH the import-bound name in brain_api.app AND the source
    # binding in brain_core.watch. ``unittest.mock.patch`` does not
    # accept ``raising=False``; the source-binding patch is a plain
    # patch — if a future refactor removes the symbol, the test fails
    # loudly (which is what we want).
    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher), patch(
        "brain_core.watch.WatchedFolderWatcher", _FakeWatcher
    ):
        with TestClient(app, base_url="http://localhost"):
            assert len(_FakeWatcher.instances) == 1
            watcher = _FakeWatcher.instances[0]
            assert watcher.observers == []
            assert watcher.start_called == 1
            assert watcher.stop_called == 0
            # And the lifespan stashed it on app.state for shutdown access.
            assert app.state.folder_watcher is watcher

    # After exit, the watcher must have been stopped.
    assert watcher.stop_called == 1


# ---------------------------------------------------------------------------
# Test 2: non-empty watched_folders → constructor receives full list
# ---------------------------------------------------------------------------


def test_lifespan_starts_watcher_with_full_folder_list(
    vault_with_folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The watcher constructor receives EVERY folder, enabled or not.

    Per the T7 contract — and per Test 4 below — enabled-filtering is the
    watcher's own responsibility (the ``WatchedFolder.enabled=False``
    rows must round-trip through a restart so toggling the switch back
    on doesn't lose state). Pin that the brain_api seam forwards the
    full list unmodified.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(
        vault_root=vault_with_folders,
        allowed_domains=("research",),
        mount_static_ui=False,
    )

    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher), patch(
        "brain_core.watch.WatchedFolderWatcher", _FakeWatcher
    ):
        with TestClient(app, base_url="http://localhost"):
            assert len(_FakeWatcher.instances) == 1
            watcher = _FakeWatcher.instances[0]
            assert len(watcher.observers) == 3
            assert {wf.enabled for wf in watcher.observers} == {True, False}
            assert watcher.start_called == 1
            # allowed_domains must be forwarded so the watcher can't
            # ingest into a scope the app isn't authorized for.
            assert watcher.allowed_domains == ("research",)


# ---------------------------------------------------------------------------
# Test 3: shutdown ordering — folder watcher stops before ConfigWatcher
# ---------------------------------------------------------------------------


def test_lifespan_stops_folder_watcher_before_config_watcher(
    vault_empty: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Folder watcher must ``stop()`` before the ConfigWatcher.

    The ConfigWatcher's ``on_change`` callback can fire up until the
    moment the observer thread joins. If the folder watcher were
    stopped AFTER the ConfigWatcher, a tail callback could attempt to
    restart a watcher we already tore down. Inverse ordering keeps that
    race impossible.

    We use a single ``call_log`` list to assert ordering rather than
    relying on stop-call counts alone.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    call_log: list[str] = []

    class _OrderedFakeFolderWatcher(_FakeWatcher):
        def stop(self) -> None:
            call_log.append("folder_watcher.stop")
            super().stop()

    config_watcher_mock = MagicMock()
    # Side effect: record the call order.
    config_watcher_mock.stop.side_effect = lambda: call_log.append("config_watcher.stop")
    config_watcher_cls = MagicMock(return_value=config_watcher_mock)

    app = create_app(
        vault_root=vault_empty,
        allowed_domains=("research",),
        mount_static_ui=False,
    )

    with patch("brain_api.app.WatchedFolderWatcher", _OrderedFakeFolderWatcher), patch(
        "brain_api.app.ConfigWatcher", config_watcher_cls
    ):
        with TestClient(app, base_url="http://localhost"):
            # During lifespan both should be live: started but not stopped.
            assert call_log == []
            config_watcher_mock.start.assert_called_once()

    # After exit, folder watcher must have stopped first.
    assert call_log == ["folder_watcher.stop", "config_watcher.stop"]
    config_watcher_mock.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4: disabled folder is forwarded to the watcher unchanged
# ---------------------------------------------------------------------------


def test_lifespan_forwards_disabled_folder_unchanged(
    vault_with_folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``enabled=False`` rows must survive the lifespan-to-watcher seam.

    The watcher's ``start()`` is responsible for skipping disabled rows
    when scheduling watchdog handlers, but the row must still be in
    the constructor's ``observers`` list so a subsequent
    ``brain_watch_folder`` config edit that re-enables it triggers a
    correct restart (the diff in :func:`_watched_folders_changed` is
    sensitive to the ``enabled`` field).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(
        vault_root=vault_with_folders,
        allowed_domains=("research",),
        mount_static_ui=False,
    )

    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher):
        with TestClient(app, base_url="http://localhost"):
            assert len(_FakeWatcher.instances) == 1
            watcher = _FakeWatcher.instances[0]
            disabled = [wf for wf in watcher.observers if not wf.enabled]
            assert len(disabled) == 1
            assert "src_three_disabled" in disabled[0].path


# ---------------------------------------------------------------------------
# Test 5: hot-reload restart bridge
# ---------------------------------------------------------------------------


def test_on_config_change_restarts_watcher_when_watched_folders_change(
    vault_empty: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_on_config_change`` must restart the watcher when watched_folders mutates.

    The brain_api hot-reload contract (Plan 16 T35) updates
    ``tool_ctx.config`` in place via ``object.__setattr__``. T7 layers
    on a watcher restart when (and only when) the new
    ``watched_folders`` list differs from the previous one. We use a
    patched ``resolve_config`` to inject a Config with a one-folder
    list; the existing watcher (zero-folder list) must be stopped + a
    fresh watcher constructed.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config_path = vault_empty / ".brain" / "config.json"

    app = create_app(vault_root=vault_empty, allowed_domains=("research",), mount_static_ui=False)

    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher):
        with TestClient(app, base_url="http://localhost"):
            # Initial watcher: empty folder list.
            assert len(_FakeWatcher.instances) == 1
            initial = _FakeWatcher.instances[0]
            assert initial.observers == []

            # Simulate a config change that adds a watched folder.
            src = vault_empty.parent / "new_src"
            src.mkdir(parents=True, exist_ok=True)
            new_config = Config(
                watched_folders=[
                    WatchedFolder(path=str(src), domain="research"),
                ],
            )

            with patch("brain_api.app.resolve_config", return_value=new_config):
                _on_config_change(config_path, app.state, vault_empty)

            # The original watcher must have been stopped.
            assert initial.stop_called == 1
            # A fresh watcher must have been constructed with the new list.
            assert len(_FakeWatcher.instances) == 2
            restart = _FakeWatcher.instances[1]
            assert len(restart.observers) == 1
            assert restart.observers[0].path == str(src)
            assert restart.start_called == 1
            # And it must be the new ``app.state.folder_watcher``.
            assert app.state.folder_watcher is restart


def test_on_config_change_skips_watcher_restart_when_watched_folders_unchanged(
    vault_empty: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config change that does NOT touch ``watched_folders`` must NOT restart.

    Restarting the observer thread on every config touch (e.g. the user
    flips ``log_llm_payloads``, or changes a domain budget) would
    needlessly churn the watcher and drop in-flight debounce timers.
    The diff in :func:`_watched_folders_changed` is the gate.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config_path = vault_empty / ".brain" / "config.json"

    app = create_app(vault_root=vault_empty, allowed_domains=("research",), mount_static_ui=False)

    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher):
        with TestClient(app, base_url="http://localhost"):
            assert len(_FakeWatcher.instances) == 1
            initial = _FakeWatcher.instances[0]
            assert initial.stop_called == 0

            # New config with same (empty) watched_folders but a different
            # unrelated field — ``log_llm_payloads=True``.
            new_config = Config(log_llm_payloads=True)
            assert list(new_config.watched_folders) == list(
                app.state.ctx.tool_ctx.config.watched_folders
            )

            with patch("brain_api.app.resolve_config", return_value=new_config):
                _on_config_change(config_path, app.state, vault_empty)

            # Watcher must NOT have been touched.
            assert initial.stop_called == 0
            assert len(_FakeWatcher.instances) == 1
            assert app.state.folder_watcher is initial


# ---------------------------------------------------------------------------
# Test 6: monkeypatch-binding regression pin (Plan 17 T17 lesson)
# ---------------------------------------------------------------------------


def test_lifespan_uses_import_bound_watched_folder_watcher_name(
    vault_empty: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin: the lifespan reads ``brain_api.app.WatchedFolderWatcher``.

    Plan 17 T17 surfaced the monkeypatch-binding gotcha: ``from X import Y``
    snapshots Y onto the importing module's namespace. Patching
    ``X.Y`` does NOT intercept callers that bound it directly. This
    test fails fast if a future refactor changes the import site
    without updating the patch targets in the rest of this file.

    Strategy: patch ONLY the import-bound name (``brain_api.app.
    WatchedFolderWatcher``); if the lifespan somehow re-resolves the
    symbol through ``brain_core.watch`` at runtime, the patch won't
    fire and ``_FakeWatcher.instances`` will be empty.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(vault_root=vault_empty, allowed_domains=("research",), mount_static_ui=False)

    # Single-site patch — no belt-and-suspenders fallback. If this
    # ever stops firing, the test fails and the import site must be
    # re-audited.
    with patch("brain_api.app.WatchedFolderWatcher", _FakeWatcher):
        with TestClient(app, base_url="http://localhost"):
            assert len(_FakeWatcher.instances) == 1, (
                "lifespan did NOT route through brain_api.app.WatchedFolderWatcher; "
                "import-bound patch did not fire — refactor regression"
            )


# ---------------------------------------------------------------------------
# Bonus: _watched_folders_changed diff predicate (cheap unit pin)
# ---------------------------------------------------------------------------


def test_watched_folders_changed_predicate(tmp_path: Path) -> None:
    """Direct unit pin on the diff predicate that gates restarts.

    The lifespan-level integration tests above exercise the predicate
    end-to-end; this pins the boundary cases directly so a future
    refactor that swaps the comparison (e.g. ``==`` vs ``model_dump``)
    surfaces here loudly rather than via a flaky integration test.
    """
    folder_a = WatchedFolder(path=str(tmp_path / "a"), domain="research")
    folder_b = WatchedFolder(path=str(tmp_path / "b"), domain="research")
    folder_a_disabled = WatchedFolder(
        path=str(tmp_path / "a"), domain="research", enabled=False
    )

    # Identity: empty == empty
    assert _watched_folders_changed([], []) is False
    # Different length
    assert _watched_folders_changed([], [folder_a]) is True
    assert _watched_folders_changed([folder_a], []) is True
    # Same paths, different enabled flag
    assert _watched_folders_changed([folder_a], [folder_a_disabled]) is True
    # Same content
    assert _watched_folders_changed([folder_a], [folder_a]) is False
    # Different path
    assert _watched_folders_changed([folder_a], [folder_b]) is True
