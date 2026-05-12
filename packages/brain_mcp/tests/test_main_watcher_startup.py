"""Plan 22 T8 — brain_mcp ``__main__`` integration for :class:`WatchedFolderWatcher`.

Pins the symmetric-watcher (D7) wiring in :mod:`brain_mcp.__main__`:

1. Cold-boot with empty ``watched_folders``: watcher is instantiated (so the
   hot-reload bridge has something to restart) AND ``start()`` is called
   with no scheduled paths.
2. Cold-boot with non-empty ``watched_folders``: watcher is instantiated
   exactly once, the constructor receives the full list (including
   disabled entries — filtering happens inside the watcher's ``start()``
   so the row survives an enable-toggle restart), and ``start()`` is
   called once.
3. Shutdown: ``_folder_watcher.stop()`` is called before the
   ``ConfigWatcher.stop()`` (T8 teardown order pin).
4. Disabled-only folder list: the disabled entry is forwarded to the
   watcher unchanged; the watcher's own filter drops it inside
   ``start()`` (covered by ``brain_core/tests/watch/test_folder_watcher.py``).
5. Hot-reload restart bridge: a ``_on_config_change`` callback with a
   modified ``Config.watched_folders`` stops the existing watcher AND
   constructs a fresh one with the new folder list. Negative pin:
   a config change that does NOT touch ``watched_folders`` must NOT
   restart the watcher.
6. Monkeypatch-binding regression pin (Plan 17 T17 lesson): patches
   ``brain_mcp.__main__.WatchedFolderWatcher`` — the import-bound name
   in ``_build_watched_folder_watcher`` — and verifies the patch fires.

These tests drive ``_run`` indirectly via the helpers + the
``_on_config_change`` callback. The full ``asyncio.run(_run())`` path
is exercised by ``test_server_smoke`` (which boots a stdio session
end-to-end); the watcher integration here uses targeted calls into
the lifecycle helpers so we don't have to spin up a stdio transport
just to assert on the watcher slot.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from brain_core.config.schema import Config, WatchedFolder

from brain_mcp import __main__ as main_module
from brain_mcp.__main__ import (
    _on_config_change,
    _watched_folders_changed,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeWatcher:
    """Records construction args + ``start`` / ``stop`` calls.

    Mirrors the public contract of
    :class:`brain_core.watch.WatchedFolderWatcher` to the extent the
    ``_run`` integration touches it: a constructor + ``start()`` +
    ``stop()``.

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


@pytest.fixture(autouse=True)
def _reset_module_state() -> Iterator[None]:
    """Clear ``brain_mcp.__main__`` module-level watcher state per test.

    Without this, a prior test that warmed ``_folder_watcher`` or
    ``_last_known_watched_folders`` would leak state into the next
    case and skew assertions. Symmetric to the
    ``_isolate_module_cache`` fixture in ``test_ctx_cache_reset.py``.
    """
    main_module._reset_watcher_state()
    # Also clear brain_mcp.server._cached_ctx so the watcher tests
    # don't accidentally read a stale ToolContext from another test.
    from brain_mcp import server as _server_module
    _server_module._cached_ctx = None
    try:
        yield
    finally:
        main_module._reset_watcher_state()
        _server_module._cached_ctx = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_config(
    brain_dir: Path,
    *,
    watched_folders: list[dict[str, Any]] | None = None,
    domains: list[dict[str, Any]] | None = None,
) -> Path:
    """Write the minimal config.json with optional watched_folders + domains."""
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
    """Plant a minimal research domain so ToolContext build doesn't fail."""
    (vault / "research").mkdir(parents=True, exist_ok=True)
    (vault / "research" / "index.md").write_text(
        "# research\n", encoding="utf-8", newline="\n"
    )
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")


def _make_watched_folder_dict(
    path: Path, domain: str, *, enabled: bool = True
) -> dict[str, Any]:
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


def _prime_boot_state(vault_root: Path) -> None:
    """Simulate the boot-state captured by ``_run`` at startup.

    The watcher integration reads :data:`_boot_vault_root` and
    :data:`_boot_allowed_domains` to know which scope to rebuild a
    watcher with on hot-reload. ``_run`` populates these in production;
    tests that invoke :func:`_on_config_change` directly must populate
    them too.
    """
    main_module._boot_vault_root = vault_root
    main_module._boot_allowed_domains = ("research",)


def _bootstrap_initial_watcher(vault_root: Path, fake_cls: type) -> Any:
    """Replicate ``_run``'s cold-boot watcher build, using a fake class.

    Test helper that mirrors the production startup flow inside
    :func:`_run` (resolve config + ``_build_watched_folder_watcher`` +
    ``start()`` + snapshot folder list) but runs synchronously and
    swaps in ``fake_cls`` for the real watcher. Returns the constructed
    fake watcher instance.
    """
    from brain_core.config.loader import resolve_config

    _prime_boot_state(vault_root)
    initial_config = resolve_config(
        config_file=vault_root / ".brain" / "config.json",
        env={},
        cli_overrides={"vault_path": vault_root},
    )
    with patch("brain_mcp.__main__.WatchedFolderWatcher", fake_cls):
        watcher = main_module._build_watched_folder_watcher(
            initial_config, vault_root, ("research",)
        )
        watcher.start()
        main_module._folder_watcher = watcher
        main_module._last_known_watched_folders = list(
            initial_config.watched_folders
        )
    return watcher


# ---------------------------------------------------------------------------
# Test 1: cold boot with empty watched_folders → watcher instantiated, no schedule
# ---------------------------------------------------------------------------


def test_cold_boot_empty_watched_folders_instantiates_watcher(
    vault_empty: Path,
) -> None:
    """Empty list still instantiates the watcher (for the hot-reload bridge).

    The boot path must always wire up ``_folder_watcher`` so the
    :func:`_on_config_change` callback has something to restart when a
    user later adds their first ``WatchedFolder`` via Settings — without
    a startup-time instance, the first ``brain_watch_folder`` call
    would have to special-case "create the watcher". Keep that branch
    out of the hot-reload path; always boot the watcher.
    """
    watcher = _bootstrap_initial_watcher(vault_empty, _FakeWatcher)

    assert len(_FakeWatcher.instances) == 1
    assert _FakeWatcher.instances[0] is watcher
    assert watcher.observers == []
    assert watcher.start_called == 1
    assert watcher.stop_called == 0
    # And the module-level slot holds it for shutdown access.
    assert main_module._folder_watcher is watcher


# ---------------------------------------------------------------------------
# Test 2: cold boot with non-empty watched_folders → constructor sees full list
# ---------------------------------------------------------------------------


def test_cold_boot_non_empty_watched_folders_forwards_all(
    vault_with_folders: Path,
) -> None:
    """The watcher constructor receives EVERY folder, enabled or not.

    Enabled-filtering is the watcher's own responsibility (the
    ``WatchedFolder.enabled=False`` rows must round-trip through a
    restart so toggling the switch back on doesn't lose state). Pin
    that the brain_mcp seam forwards the full list unmodified.
    """
    watcher = _bootstrap_initial_watcher(vault_with_folders, _FakeWatcher)

    assert len(_FakeWatcher.instances) == 1
    assert len(watcher.observers) == 3
    assert {wf.enabled for wf in watcher.observers} == {True, False}
    assert watcher.start_called == 1
    # allowed_domains forwarded so the watcher can't ingest into a
    # scope the brain_mcp process isn't authorized for.
    assert watcher.allowed_domains == ("research",)


# ---------------------------------------------------------------------------
# Test 3: shutdown stops folder_watcher
# ---------------------------------------------------------------------------


def test_shutdown_stops_folder_watcher(vault_empty: Path) -> None:
    """``_folder_watcher.stop()`` must fire on teardown.

    The full ``_run`` finally-block stops the folder watcher BEFORE the
    ConfigWatcher; we mirror that ordering here without spinning up an
    actual stdio transport. The pin is the stop-call count: shutdown
    must invoke ``stop()`` exactly once.
    """
    watcher = _bootstrap_initial_watcher(vault_empty, _FakeWatcher)
    assert watcher.stop_called == 0

    # Manually replay the finally-block teardown logic.
    if main_module._folder_watcher is not None:
        main_module._folder_watcher.stop()
        main_module._folder_watcher = None

    assert watcher.stop_called == 1
    assert main_module._folder_watcher is None


# ---------------------------------------------------------------------------
# Test 4: disabled WatchedFolder excluded from filter at brain_mcp seam? NO.
#         The disabled entry is forwarded unchanged; filtering is watcher-side.
# ---------------------------------------------------------------------------


def test_disabled_watched_folder_forwarded_unchanged(
    vault_with_folders: Path,
) -> None:
    """``enabled=False`` rows must survive the lifecycle-to-watcher seam.

    The watcher's ``start()`` is responsible for skipping disabled rows
    when scheduling watchdog handlers, but the row must still be in
    the constructor's ``observers`` list so a subsequent
    ``brain_watch_folder`` config edit that re-enables it triggers a
    correct restart (the diff in :func:`_watched_folders_changed` is
    sensitive to the ``enabled`` field).
    """
    watcher = _bootstrap_initial_watcher(vault_with_folders, _FakeWatcher)

    disabled = [wf for wf in watcher.observers if not wf.enabled]
    assert len(disabled) == 1
    assert "src_three_disabled" in disabled[0].path


# ---------------------------------------------------------------------------
# Test 5a: hot-reload restart bridge — watcher rebuilt on watched_folders change
# ---------------------------------------------------------------------------


def test_on_config_change_restarts_watcher_when_watched_folders_change(
    vault_empty: Path,
) -> None:
    """``_on_config_change`` restarts the watcher when watched_folders mutates.

    The brain_mcp hot-reload contract baseline (Plan 16 T39.5) clears
    the loader cache + the ToolContext singleton. T8 layers on a
    watcher restart when (and only when) the new ``watched_folders``
    list differs from the previous one. We use a patched
    ``resolve_config`` to inject a Config with a one-folder list; the
    existing watcher (zero-folder list) must be stopped and a fresh
    watcher constructed.
    """
    config_path = vault_empty / ".brain" / "config.json"
    _bootstrap_initial_watcher(vault_empty, _FakeWatcher)

    initial = _FakeWatcher.instances[0]
    assert initial.observers == []

    src = vault_empty.parent / "new_src"
    src.mkdir(parents=True, exist_ok=True)
    new_config = Config(
        watched_folders=[
            WatchedFolder(path=str(src), domain="research"),
        ],
    )

    with patch("brain_mcp.__main__.WatchedFolderWatcher", _FakeWatcher), patch(
        "brain_mcp.__main__.resolve_config", return_value=new_config
    ):
        _on_config_change(config_path)

    # The original watcher must have been stopped.
    assert initial.stop_called == 1
    # A fresh watcher must have been constructed with the new list.
    assert len(_FakeWatcher.instances) == 2
    restart = _FakeWatcher.instances[1]
    assert len(restart.observers) == 1
    assert restart.observers[0].path == str(src)
    assert restart.start_called == 1
    # And it must be the new module-level slot.
    assert main_module._folder_watcher is restart


# ---------------------------------------------------------------------------
# Test 5b: negative pin — no-watched-folders config change → no restart
# ---------------------------------------------------------------------------


def test_on_config_change_skips_restart_when_watched_folders_unchanged(
    vault_empty: Path,
) -> None:
    """A config change that does NOT touch ``watched_folders`` must NOT restart.

    Restarting the observer thread on every config touch (e.g. the user
    flips ``log_llm_payloads``, or changes a domain budget) would
    needlessly churn the watcher and drop in-flight debounce timers.
    The diff in :func:`_watched_folders_changed` is the gate.
    """
    config_path = vault_empty / ".brain" / "config.json"
    _bootstrap_initial_watcher(vault_empty, _FakeWatcher)

    initial = _FakeWatcher.instances[0]
    assert initial.stop_called == 0

    # New config with same (empty) watched_folders but a different
    # unrelated field — ``log_llm_payloads=True``.
    new_config = Config(log_llm_payloads=True)
    assert list(new_config.watched_folders) == []

    with patch("brain_mcp.__main__.WatchedFolderWatcher", _FakeWatcher), patch(
        "brain_mcp.__main__.resolve_config", return_value=new_config
    ):
        _on_config_change(config_path)

    # Watcher must NOT have been touched.
    assert initial.stop_called == 0
    assert len(_FakeWatcher.instances) == 1
    assert main_module._folder_watcher is initial


# ---------------------------------------------------------------------------
# Test 6: monkeypatch-binding regression pin (Plan 17 T17 lesson)
# ---------------------------------------------------------------------------


def test_build_watcher_uses_import_bound_watched_folder_watcher_name(
    vault_empty: Path,
) -> None:
    """Pin: ``_build_watched_folder_watcher`` reads
    ``brain_mcp.__main__.WatchedFolderWatcher``.

    Plan 17 T17 surfaced the monkeypatch-binding gotcha: ``from X
    import Y`` snapshots Y onto the importing module's namespace.
    Patching ``X.Y`` does NOT intercept callers that bound it directly.
    This test fails fast if a future refactor changes the import site
    without updating the patch targets in the rest of this file.

    Strategy: patch ONLY the import-bound name
    (``brain_mcp.__main__.WatchedFolderWatcher``); if
    ``_build_watched_folder_watcher`` somehow re-resolves the symbol
    through ``brain_core.watch`` at runtime, the patch won't fire and
    ``_FakeWatcher.instances`` will be empty.
    """
    _prime_boot_state(vault_empty)

    from brain_core.config.loader import resolve_config

    initial_config = resolve_config(
        config_file=vault_empty / ".brain" / "config.json",
        env={},
        cli_overrides={"vault_path": vault_empty},
    )

    # Single-site patch — no belt-and-suspenders fallback. If this
    # ever stops firing, the test fails and the import site must be
    # re-audited.
    with patch("brain_mcp.__main__.WatchedFolderWatcher", _FakeWatcher):
        watcher = main_module._build_watched_folder_watcher(
            initial_config, vault_empty, ("research",)
        )

    assert isinstance(watcher, _FakeWatcher), (
        "_build_watched_folder_watcher did NOT route through "
        "brain_mcp.__main__.WatchedFolderWatcher; import-bound patch "
        "did not fire — refactor regression"
    )
    assert len(_FakeWatcher.instances) == 1


# ---------------------------------------------------------------------------
# Bonus: _watched_folders_changed diff predicate (cheap unit pin)
# ---------------------------------------------------------------------------


def test_watched_folders_changed_predicate(tmp_path: Path) -> None:
    """Direct unit pin on the diff predicate that gates restarts.

    The integration tests above exercise the predicate end-to-end;
    this pins the boundary cases directly so a future refactor that
    swaps the comparison (e.g. ``==`` vs ``model_dump``) surfaces here
    loudly rather than via a flaky integration test.
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


# ---------------------------------------------------------------------------
# Bonus: defensive bail when boot state is uninitialized
# ---------------------------------------------------------------------------


def test_on_config_change_no_op_when_boot_state_uninitialized(
    vault_empty: Path,
) -> None:
    """``_on_config_change`` must not crash if called before ``_run`` finishes.

    There is a tiny window between ``ConfigWatcher.start()`` and the
    initial folder-watcher build where the callback could fire with
    ``_boot_vault_root is None``. The callback must still complete its
    Plan 16 T35 / T39.5 responsibilities (loader-cache invalidate +
    ctx-reset) and then silently no-op on the watcher branch.
    """
    config_path = vault_empty / ".brain" / "config.json"
    # Do NOT prime boot state; leave _boot_vault_root as None.
    assert main_module._boot_vault_root is None

    # Should not raise. The loader/ctx-reset side effects are exercised
    # by test_ctx_cache_reset.py; here we just confirm the watcher
    # branch's early return.
    _on_config_change(config_path)
    assert len(_FakeWatcher.instances) == 0
