"""Pin the structured warning that fires when the SPA mount is skipped — Plan 21 Task 2.

Plan 21 Task 1 hardened ``resolve_out_dir`` with a repo walk-up so the
common iCloud + uv editable install case no longer silently misses the
``apps/brain_web/out`` directory. But a resolver failure can still happen
under genuinely degraded environments (no build, no env override, walk-up
exhausted), and the previous bare ``except RuntimeError: pass`` in
``create_app`` swallowed it without a sound. Task 2 replaces the silent
no-op with a structured ``log.warning`` so a developer running visual QA
sees the cause immediately instead of debugging an opaque ``GET /`` 404.

Three pins:

1. **Warning fires when the resolver raises AND ``mount_static_ui=True``** —
   payload carries the original error message AND a hint string pointing
   at the ``BRAIN_WEB_OUT_DIR`` env-override workaround.
2. **Warning does NOT fire when ``mount_static_ui=False``** — the early
   skip-branch (Plan 13 Task 5) bypasses the try-block entirely; CI /
   contract tests / headless deploys stay silent.
3. **Warning does NOT fire when the resolver succeeds** — successful
   mount path is silent; the warning is a degraded-mode signal only.

Plan 17 T17 monkeypatch-binding lesson applies: ``brain_api.app`` does
``from brain_api.static_ui import resolve_out_dir`` so the name lives in
``brain_api.app`` as a module-level binding, NOT a dynamic lookup against
``brain_api.static_ui``. Patching ``brain_api.static_ui.resolve_out_dir``
does NOT intercept the import-bound reference. These tests patch
``brain_api.app.resolve_out_dir`` directly. (We also patch
``brain_api.static_ui.resolve_out_dir`` with ``raising=False`` as
belt-and-suspenders coverage in case a future refactor inlines the
import.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import structlog
from brain_api import create_app


def _raising_resolver() -> Path:
    """Stand-in for ``resolve_out_dir`` that always fails with a RuntimeError.

    Mirrors the shape of the real ``resolve_out_dir`` failure path so the
    ``except RuntimeError`` branch in ``create_app`` catches it normally.
    """
    raise RuntimeError("simulated resolver failure")


def test_silent_degrade_warning_fires_when_resolve_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mount_static_ui=True`` + resolver raises → ``spa_mount_skipped`` warning logged.

    Asserts the event name, the embedded error message, and the hint
    string that points the developer at the ``BRAIN_WEB_OUT_DIR``
    env-override workaround. Without this warning, the same condition
    would surface as an opaque ``GET /`` 404 at first browser load with
    no log trace of why the SPA mount was skipped.
    """
    # Plan 17 T17: patch the import-bound name in brain_api.app, not the
    # source module brain_api.static_ui (which does NOT intercept).
    monkeypatch.setattr("brain_api.app.resolve_out_dir", _raising_resolver)
    # Belt-and-suspenders: patch the source binding too in case a future
    # refactor inlines the import. raising=False so this stays compatible
    # if the attribute layout shifts.
    monkeypatch.setattr(
        "brain_api.static_ui.resolve_out_dir",
        _raising_resolver,
        raising=False,
    )

    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    with structlog.testing.capture_logs() as captured:
        create_app(
            vault_root=vault,
            allowed_domains=("research",),
            mount_static_ui=True,
        )

    skipped = [
        event for event in captured if event.get("event") == "spa_mount_skipped"
    ]
    assert len(skipped) == 1, (
        f"expected exactly one spa_mount_skipped warning; got {captured!r}"
    )
    event = skipped[0]
    assert event["log_level"] == "warning"
    assert event["error"] == "simulated resolver failure"
    # Hint must name the env-override workaround AND the build fallback so
    # the developer has two unambiguous next actions.
    assert "BRAIN_WEB_OUT_DIR" in event["hint"]
    assert "pnpm --dir apps/brain_web build" in event["hint"]


def test_silent_degrade_warning_does_not_fire_when_mount_static_ui_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mount_static_ui=False`` → no warning, even when the resolver would raise.

    The Plan 13 Task 5 skip-branch returns before the try-block; the
    test fixture path (CI, contract tests, headless deploys) MUST stay
    silent so log noise doesn't pollute green test runs. We monkeypatch
    the resolver to raise to prove the suppression isn't accidental —
    if the skip-branch ever reordered to fire the try-block first, this
    test catches it.
    """
    monkeypatch.setattr("brain_api.app.resolve_out_dir", _raising_resolver)
    monkeypatch.setattr(
        "brain_api.static_ui.resolve_out_dir",
        _raising_resolver,
        raising=False,
    )

    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    with structlog.testing.capture_logs() as captured:
        create_app(
            vault_root=vault,
            allowed_domains=("research",),
            mount_static_ui=False,
        )

    skipped = [
        event for event in captured if event.get("event") == "spa_mount_skipped"
    ]
    assert skipped == [], (
        f"expected zero spa_mount_skipped warnings under mount_static_ui=False; "
        f"got {skipped!r}"
    )


def test_silent_degrade_warning_does_not_fire_on_successful_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful resolver → no warning. The happy path stays quiet.

    Build a miniature ``out/`` directory with an ``index.html`` so the
    real resolver (via ``BRAIN_WEB_OUT_DIR``) succeeds; ``create_app``
    mounts the SPA and the warning branch never executes. Mirrors the
    setup in ``test_app_static_mount.test_default_create_app_static_mount_present_when_resolver_succeeds``.
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

    with structlog.testing.capture_logs() as captured:
        create_app(
            vault_root=vault,
            allowed_domains=("research",),
            mount_static_ui=True,
        )

    skipped = [
        event for event in captured if event.get("event") == "spa_mount_skipped"
    ]
    assert skipped == [], (
        f"expected zero spa_mount_skipped warnings on successful mount; "
        f"got {skipped!r}"
    )
