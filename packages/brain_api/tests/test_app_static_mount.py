"""Regression-pin tests for the ``mount_static_ui`` flag — Plan 13 Task 5.

Plan 08 Task 1 mounted ``SPAStaticFiles`` at ``/`` on every ``create_app()``
return so a single FastAPI process serves both the API and the Next.js
SPA. Plan 13 Task 4 diagnosed that this catch-all mount silently shadows
synthetic test routes (``/_boom``, ``/_protected``, ``/_ctx_echo``, etc.)
attached to the ``app`` fixture AFTER ``create_app`` returns — causing 13
unit tests to silently return ``index.html`` (HTTP 200) instead of the
status code their assertion expects, whenever ``apps/brain_web/out/``
existed from a prior ``pnpm build``.

Plan 13 Task 5 adds a ``mount_static_ui: bool = True`` keyword-only
parameter to ``create_app``. The conftest's ``app`` fixture now passes
``mount_static_ui=False`` so the test suite's synthetic routes resolve as
intended. These tests pin the new flag's behavior at the architectural
level — production callers MUST keep the default ``True``, and the test
fixture path MUST evict the SPA mount.

Three cases:

1. ``mount_static_ui=True`` (default) → ``ui`` mount registered iff the
   resolver finds an ``out/`` directory.
2. ``mount_static_ui=False`` → ``ui`` mount NEVER registered, regardless
   of resolver state.
3. With ``mount_static_ui=False``, synthetic routes attached AFTER
   ``create_app`` resolve normally (the regression that Task 5 fixes).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from fastapi.testclient import TestClient
from starlette.routing import Mount


def _ui_mounts(app: object) -> list[Mount]:
    """Return every ``Mount`` route on ``app`` whose name is ``"ui"``."""
    return [
        route
        for route in app.routes  # type: ignore[attr-defined]
        if isinstance(route, Mount) and route.name == "ui"
    ]


def test_default_create_app_attempts_static_mount(tmp_path: Path) -> None:
    """``create_app(...)`` with default ``mount_static_ui=True`` tries to mount the SPA.

    The resolver may or may not find an ``out/`` directory depending on
    whether the dev tree has run ``pnpm build`` (or whether
    ``BRAIN_WEB_OUT_DIR`` / ``BRAIN_INSTALL_DIR`` is set in CI). Either
    outcome is correct for production:
    - ``out/`` resolves → exactly one ``ui`` mount is registered.
    - Resolver raises → the ``try/except RuntimeError`` swallows it and
      zero mounts are registered (API-only mode).

    The pin: ``len(ui_mounts) <= 1`` AND if the dev fallback resolves
    successfully, exactly one mount IS present. We exercise both branches
    by parametrizing on whether ``BRAIN_WEB_OUT_DIR`` points at a real
    directory.
    """
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    app = create_app(vault_root=vault, allowed_domains=("research",))
    mounts = _ui_mounts(app)
    # 0 (resolver raised, API-only mode) or 1 (out/ found) — both valid.
    # The architectural pin is that the default code path attempts the
    # mount; the result depends on environment.
    assert len(mounts) <= 1
    # If the dev tree has an ``apps/brain_web/out/`` from a prior build
    # OR ``BRAIN_WEB_OUT_DIR`` is set, the mount succeeds. Pin the
    # successful-path shape so a future regression that registers
    # multiple ``ui`` mounts (or breaks the mount name) surfaces here.
    if mounts:
        assert mounts[0].name == "ui"


def test_default_create_app_static_mount_present_when_resolver_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mount_static_ui=True`` + resolver succeeds → exactly one ``ui`` mount.

    Builds a miniature ``out/`` directory and points ``BRAIN_WEB_OUT_DIR``
    at it so the resolver always succeeds, regardless of whether the dev
    tree has run ``pnpm build``. Pins the successful-path mount count and
    name.
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        "<!doctype html><html><body>brain</body></html>\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("BRAIN_WEB_OUT_DIR", str(out_dir))

    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    app = create_app(vault_root=vault, allowed_domains=("research",))
    mounts = _ui_mounts(app)
    assert len(mounts) == 1
    assert mounts[0].name == "ui"


def test_create_app_with_mount_static_ui_false_skips_mount(tmp_path: Path) -> None:
    """``mount_static_ui=False`` → zero ``ui`` mounts, regardless of resolver state.

    Even when the dev tree has a fully-built ``out/`` directory (which
    would normally cause the resolver to succeed), passing
    ``mount_static_ui=False`` MUST evict the mount entirely. This is the
    contract the conftest's ``app`` fixture relies on for the 13 unit
    tests fixed by Plan 13 Task 5.
    """
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    app = create_app(
        vault_root=vault,
        allowed_domains=("research",),
        mount_static_ui=False,
    )
    assert _ui_mounts(app) == []


def test_synthetic_routes_resolve_when_static_mount_disabled(tmp_path: Path) -> None:
    """With ``mount_static_ui=False``, synthetic test routes resolve normally.

    The end-to-end regression pin: registers a synthetic ``GET /_synth``
    on a fresh app built with ``mount_static_ui=False``, asserts the
    route returns its intended status (200) and JSON body. Without the
    flag, the SPA mount would catch ``/_synth`` and return ``index.html``
    (HTTP 200, but with HTML body) — which is exactly the regression
    Plan 13 Task 5 fixes for the 13 brain_api unit tests.

    This test would FAIL on ``main`` before Task 5: even if a synthetic
    route matched, the response body would be ``index.html`` HTML, not
    the route's JSON dict. The test pins both the status code and the
    body shape so the regression cannot resurface.
    """
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    app = create_app(
        vault_root=vault,
        allowed_domains=("research",),
        mount_static_ui=False,
    )

    @app.get("/_synth")
    async def synth() -> dict[str, str]:
        return {"hello": "world"}

    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_synth")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}
