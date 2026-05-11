"""Plan 17 Task 2 — brain_api ConfigWatcher live ctx.config hot-reload tests.

Pins four properties of the :func:`~brain_api.app._on_config_change` callback
and the lifespan watcher wiring:

1. Happy-path update: calling ``_on_config_change`` with a patched
   ``resolve_config`` pushes the new Config onto ``app.state.ctx.tool_ctx.config``.
2. Identity preservation: neither ``app.state.ctx`` nor ``app.state.ctx.tool_ctx``
   is replaced — only the ``config`` field is swapped in-place.
3. Failure isolation: a ``resolve_config`` that raises must NOT propagate; the
   old config must remain intact.
4. Watcher cleanup: the lifespan calls ``config_watcher.stop()`` on exit
   (verified via ``unittest.mock.patch``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from brain_api.app import _on_config_change, create_app
from brain_core.config.schema import Config
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_config(brain_dir: Path) -> Path:
    """Write the minimal config.json that ``resolve_config`` accepts."""
    brain_dir.mkdir(parents=True, exist_ok=True)
    config_path = brain_dir / "config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    return config_path


def _seed_vault(vault: Path) -> None:
    """Plant a minimal research domain so ``build_app_context`` doesn't fail."""
    (vault / "research").mkdir(parents=True, exist_ok=True)
    (vault / "research" / "index.md").write_text(
        "# research\n", encoding="utf-8", newline="\n"
    )
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """A minimal vault with a seeded config.json."""
    v = tmp_path / "vault"
    _seed_vault(v)
    _write_minimal_config(v / ".brain")
    return v


@pytest.fixture()
def running_app(vault: Path, monkeypatch: pytest.MonkeyPatch):
    """A started TestClient (lifespan runs) bound to *vault*.

    ``mount_static_ui=False`` keeps the test surface clean (no SPA catch-all).
    ``ANTHROPIC_API_KEY`` is cleared so the lifespan stays in FakeLLMProvider
    territory — no outbound calls.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(vault_root=vault, allowed_domains=("research",), mount_static_ui=False)
    with TestClient(app, base_url="http://localhost") as client:
        yield client, app


# ---------------------------------------------------------------------------
# Test 1: happy-path update
# ---------------------------------------------------------------------------


def test_on_config_change_updates_tool_ctx_config(
    vault: Path, running_app: tuple
) -> None:
    """Calling ``_on_config_change`` replaces ``tool_ctx.config`` with the new Config.

    The new Config is produced by a patched ``resolve_config`` that returns a
    distinguishable sentinel object; after the call, ``ctx.tool_ctx.config`` must
    be that sentinel.
    """
    _client, app = running_app
    config_path = vault / ".brain" / "config.json"

    new_config = Config()  # fresh, distinct object

    with patch("brain_api.app.resolve_config", return_value=new_config):
        _on_config_change(config_path, app.state, vault)

    assert app.state.ctx.tool_ctx.config is new_config


# ---------------------------------------------------------------------------
# Test 2: identity preservation
# ---------------------------------------------------------------------------


def test_on_config_change_preserves_ctx_and_tool_ctx_identity(
    vault: Path, running_app: tuple
) -> None:
    """``ctx`` and ``ctx.tool_ctx`` must not be replaced — only ``config`` swaps.

    If the callback accidentally reconstructed AppContext or ToolContext, routes
    holding a reference from a prior ``Depends(get_ctx)`` call would see stale
    state. Pin that the container objects are the same Python objects before and
    after the callback.
    """
    _client, app = running_app
    config_path = vault / ".brain" / "config.json"

    ctx_before = app.state.ctx
    tool_ctx_before = app.state.ctx.tool_ctx

    new_config = Config()

    with patch("brain_api.app.resolve_config", return_value=new_config):
        _on_config_change(config_path, app.state, vault)

    assert app.state.ctx is ctx_before, "AppContext must not be replaced"
    assert app.state.ctx.tool_ctx is tool_ctx_before, "ToolContext must not be replaced"


# ---------------------------------------------------------------------------
# Test 3: failure isolation
# ---------------------------------------------------------------------------


def test_on_config_change_swallows_resolve_error(
    vault: Path, running_app: tuple
) -> None:
    """A ``resolve_config`` failure must NOT propagate and must preserve the old config.

    The watcher runs on a background thread; an unhandled exception there
    would crash the thread silently without surfacing to the caller. But even
    if caught at the threading layer, a propagating exception would mean the
    old config is gone and the field is left in an intermediate state.  Pin
    that the callback swallows the error and leaves ``tool_ctx.config`` intact.
    """
    _client, app = running_app
    config_path = vault / ".brain" / "config.json"

    config_before = app.state.ctx.tool_ctx.config

    with patch("brain_api.app.resolve_config", side_effect=RuntimeError("disk read failed")):
        # Must not raise
        _on_config_change(config_path, app.state, vault)

    assert app.state.ctx.tool_ctx.config is config_before, (
        "config must be unchanged after a resolve failure"
    )


# ---------------------------------------------------------------------------
# Test 4: watcher cleanup
# ---------------------------------------------------------------------------


def test_lifespan_calls_watcher_stop_on_exit(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lifespan must call ``ConfigWatcher.stop()`` when the app shuts down.

    We patch ``ConfigWatcher`` with a ``MagicMock`` instance and verify
    ``stop()`` was called exactly once after the TestClient context-manager exits
    (which triggers the lifespan's ``finally`` block).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_watcher = MagicMock()
    mock_watcher_cls = MagicMock(return_value=mock_watcher)

    app = create_app(vault_root=vault, allowed_domains=("research",), mount_static_ui=False)

    with patch("brain_api.app.ConfigWatcher", mock_watcher_cls):
        with TestClient(app, base_url="http://localhost"):
            # Lifespan is active; watcher should be started but not stopped yet.
            mock_watcher.start.assert_called_once()
            mock_watcher.stop.assert_not_called()

    # After exit, ``finally`` block must have called ``stop()``.
    mock_watcher.stop.assert_called_once()
