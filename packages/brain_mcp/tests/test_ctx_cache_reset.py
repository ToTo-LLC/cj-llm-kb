"""Plan 16 Task 39.5 — brain_mcp ConfigWatcher clears the cached ToolContext.

Pre-T39.5, ``_cached_ctx`` was a closure local inside :func:`create_server`.
The watcher's ``on_change`` invalidated the loader's cache but
``_build_ctx_lazy`` still returned the cached ToolContext with stale
``.config`` — the watcher only ever benefitted the FIRST tool call per
process. Post-T39.5:

1. ``_cached_ctx`` lives at module scope so the watcher can reach it.
2. :func:`_reset_ctx_cache` clears the singleton; the next dispatch rebuilds.
3. ``__main__._run`` chains ``invalidate_cache_for(...) → _reset_ctx_cache()``
   in the ConfigWatcher's ``on_change`` callback.

Pin tests below:

* :func:`_reset_ctx_cache` clears the singleton (unit-level).
* End-to-end via the watcher: write a new config to disk → after debounce,
  the cached ToolContext is cleared so the next ``_build_ctx`` rebuild
  picks up the new state.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.config.hot_reload import ConfigWatcher
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext
from brain_mcp import server as server_module
from brain_mcp.__main__ import _on_config_change
from brain_mcp.server import _reset_ctx_cache, create_server


@pytest.fixture(autouse=True)
def _isolate_module_cache() -> Iterator[None]:
    """Clear the module-level ``_cached_ctx`` before AND after each test.

    Without this, a prior test that warmed the cache (e.g. via
    ``test_server_smoke``) would let the next test see a stale singleton
    and skew assertions. The watcher tests in this module also depend on
    a clean starting state.
    """
    server_module._cached_ctx = None
    try:
        yield
    finally:
        server_module._cached_ctx = None


def test_reset_ctx_cache_clears_singleton(seeded_vault: Path) -> None:
    """``_reset_ctx_cache()`` returns the module-level cache to ``None``.

    Warm the cache by triggering one ``list_tools`` build path (we go
    through ``create_server`` + the lazy ``_build_ctx`` reachable via the
    server's tool dispatcher, but the simplest production-shape exercise is
    to directly populate ``_cached_ctx`` and call the reset helper).
    """
    # Warm the singleton with a sentinel ToolContext. Identity comparison
    # against the sentinel proves the reset cleared THIS object — not just
    # that the slot is None for some other reason.
    sentinel = ToolContext(
        vault_root=seeded_vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=Config(vault_path=seeded_vault),
    )
    server_module._cached_ctx = sentinel
    assert server_module._cached_ctx is sentinel

    _reset_ctx_cache()
    assert server_module._cached_ctx is None


def test_reset_ctx_cache_is_idempotent() -> None:
    """Two consecutive ``_reset_ctx_cache()`` calls collapse to the same state.

    Rapid config saves can fire ``on_change`` multiple times in quick
    succession; the second-and-later calls must be cheap no-ops.
    """
    server_module._cached_ctx = None
    _reset_ctx_cache()
    _reset_ctx_cache()
    assert server_module._cached_ctx is None


def test_watcher_chained_callback_clears_cache_end_to_end(
    seeded_vault: Path,
) -> None:
    """End-to-end: a config-file change triggers ``_reset_ctx_cache``.

    Calls the same ``_on_config_change`` callback the production
    ``__main__._run`` wires into the watcher. We set up the watcher
    pointing at a real config path, warm ``_cached_ctx`` with a
    sentinel, write the config to trigger the debounce timer, and
    assert the cache cleared.
    """
    config_path = seeded_vault / ".brain" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    fired = threading.Event()

    def _on_change() -> None:
        _on_config_change(config_path)
        fired.set()

    watcher = ConfigWatcher(
        config_path=config_path,
        on_change=_on_change,
        debounce_seconds=0.05,
    )

    # Warm the cache with a sentinel ToolContext so we can prove the
    # callback cleared it (rather than just observing a never-set slot).
    sentinel = ToolContext(
        vault_root=seeded_vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=Config(vault_path=seeded_vault),
    )
    server_module._cached_ctx = sentinel

    watcher.start()
    try:
        # Write a config to trigger the watcher. Debounce window is 50ms;
        # event timing isn't guaranteed across CI runners, so we wait up
        # to 5 seconds for the chained callback to fire.
        config_path.write_text(
            json.dumps({"log_llm_payloads": True}),
            encoding="utf-8",
            newline="\n",
        )
        # Some watchdog backends miss the initial create when a file did
        # not previously exist — bump the file with a follow-up modify
        # to guarantee an event lands within the window.
        time.sleep(0.1)
        config_path.write_text(
            json.dumps({"log_llm_payloads": False}),
            encoding="utf-8",
            newline="\n",
        )
        assert fired.wait(timeout=5.0), (
            "watcher's on_change callback did not fire within 5s — "
            "either the watchdog backend dropped the event or the "
            "debounce window swallowed it"
        )
    finally:
        watcher.stop()

    # The chained callback ran → _cached_ctx is None.
    assert server_module._cached_ctx is None


def test_create_server_uses_module_level_cache(seeded_vault: Path) -> None:
    """Smoke check: ``create_server`` still works after the closure → module
    refactor. The Plan 16 Task 39.5 change moved ``_cached_ctx`` from a
    closure local to a module-level singleton; this pin guards against a
    regression where ``_build_ctx`` is wired to the wrong scope.
    """
    server = create_server(vault_root=seeded_vault, allowed_domains=("research",))
    # Server constructed without raising — the closure refactor preserved
    # the construction path. The module-level cache slot is still None
    # (lazy build hasn't fired) until a tool call goes through the
    # dispatcher; that path is exercised exhaustively by the rest of
    # the brain_mcp tool tests.
    assert server is not None
    assert server_module._cached_ctx is None
