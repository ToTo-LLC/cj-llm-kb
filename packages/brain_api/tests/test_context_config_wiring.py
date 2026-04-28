"""Plan 11 Task 7 polish — wire Config into brain_api ToolContext.

Pins three properties of the build_app_context → lifespan → ToolContext path:

1. ``build_app_context(..., config=cfg)`` stores ``cfg`` on
   ``ctx.tool_ctx.config`` BY IDENTITY (no ``model_copy``). The mutation tools
   in :mod:`brain_core.tools.config_set` (and friends) mutate Config in place
   and rely on the caller's reference observing the change after the call
   returns — copying would break read-after-write.

2. The :func:`brain_api.app._lifespan` loads Config via
   :func:`brain_core.config.loader.load_config` on startup and threads it
   through to ``ctx.tool_ctx.config``. A populated ``config.json`` in the
   vault round-trips to the live AppContext.

3. First-run boot with NO ``config.json`` on disk still succeeds — the
   loader's Plan 11 D7 fallback chain (config.json → .bak → defaults)
   returns a default :class:`Config` and the lifespan threads it through
   without crashing.

Without this wiring, every Plan 11 mutation tool dispatched via brain_web →
brain_api lands on the ``ctx.config is None`` no-op branch: the toast says
"saved" but the disk write never happens.
"""

from __future__ import annotations

import json
from pathlib import Path

from brain_api import create_app
from brain_api.context import build_app_context
from brain_core.config.schema import Config, DomainOverride
from fastapi.testclient import TestClient


def test_build_app_context_preserves_config_identity(seeded_vault: Path) -> None:
    """The Config passed in is the SAME instance ctx.tool_ctx.config references.

    Identity (``is``) — not equality. The mutation tools rely on observing
    in-place edits made by other layers within the same process; a defensive
    ``model_copy`` on the wiring boundary would silently break that contract.
    """
    cfg = Config(
        domains=["research", "work", "personal", "hobby"],
        active_domain="hobby",
        domain_overrides={
            "hobby": DomainOverride(classify_model="claude-haiku-4-5-20251001"),
        },
    )

    ctx = build_app_context(
        vault_root=seeded_vault,
        allowed_domains=("research", "hobby"),
        config=cfg,
    )

    # Identity check — the ToolContext stores the exact same Config instance.
    # ``is`` not ``==`` is load-bearing here.
    assert ctx.tool_ctx.config is cfg
    # Round-trip a few fields so a future field addition that breaks the
    # passthrough fails loudly here, not on the next user-visible save.
    assert ctx.tool_ctx.config.active_domain == "hobby"
    assert ctx.tool_ctx.config.domain_overrides["hobby"].classify_model == (
        "claude-haiku-4-5-20251001"
    )


def test_build_app_context_default_config_is_none(seeded_vault: Path) -> None:
    """Omitting ``config=`` leaves ``ctx.tool_ctx.config`` at None.

    Existing brain_api tests construct AppContext without passing Config —
    they MUST keep working. The mutation tools' ``ctx.config is None`` no-op
    branch is what those tests exercise; if this test ever fails, every
    pre-existing brain_api test that doesn't care about persistence will
    break in confusing ways.
    """
    ctx = build_app_context(
        vault_root=seeded_vault,
        allowed_domains=("research",),
    )
    assert ctx.tool_ctx.config is None


def test_lifespan_loads_config_from_disk(seeded_vault: Path) -> None:
    """A populated config.json on disk round-trips through the lifespan.

    Writes a config.json with a known domain override into the vault BEFORE
    starting the app, then verifies the lifespan-built ctx exposes the same
    override. This is the production-shape test — it pins the full
    ``load_config(...) → build_app_context(config=...) → ctx.tool_ctx.config``
    pipeline that Plan 11 mutation tools need to round-trip.
    """
    brain_dir = seeded_vault / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = brain_dir / "config.json"
    # Hand-craft a minimal persisted blob — only fields in
    # ``Config._PERSISTED_FIELDS``. ``vault_path`` is sourced separately
    # by the lifespan's ``cli_overrides`` and is NOT in the file.
    cfg_path.write_text(
        json.dumps(
            {
                "domains": ["research", "work", "personal"],
                "active_domain": "research",
                "domain_overrides": {
                    "research": {"classify_model": "claude-haiku-4-5-20251001"},
                },
            }
        ),
        encoding="utf-8",
        newline="\n",
    )

    app = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        # Hit /healthz so we know the lifespan ran cleanly before we read
        # ctx state — otherwise a lifespan crash would surface as a confusing
        # AttributeError instead of a useful 500.
        assert client.get("/healthz").status_code == 200
        ctx = app.state.ctx
        assert ctx.tool_ctx.config is not None
        assert ctx.tool_ctx.config.active_domain == "research"
        assert "research" in ctx.tool_ctx.config.domain_overrides
        assert ctx.tool_ctx.config.domain_overrides["research"].classify_model == (
            "claude-haiku-4-5-20251001"
        )
        # vault_path is the chicken-and-egg field — the lifespan supplies it
        # via cli_overrides, so it should match the seeded vault even though
        # it was NOT in config.json.
        assert ctx.tool_ctx.config.vault_path == seeded_vault


def test_lifespan_boots_with_no_config_json(seeded_vault: Path) -> None:
    """First-run: no config.json on disk → loader falls back to defaults.

    The Plan 11 D7 fallback chain (config.json → .bak → ``Config()`` defaults)
    means a fresh vault with no config.json must still boot. Without this,
    every fresh install would crash on first start.
    """
    # seeded_vault has NO .brain/config.json by default (the fixture only
    # seeds research/, work/, personal/ markdown). Sanity-check that, then
    # boot the app and confirm we got a default Config.
    cfg_path = seeded_vault / ".brain" / "config.json"
    assert not cfg_path.exists(), (
        "preconditions: seeded_vault must NOT have config.json for this test"
    )

    app = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/healthz").status_code == 200
        ctx = app.state.ctx
        # Defaults applied — ``active_domain`` defaults to "research" and
        # ``domain_overrides`` defaults to {} per Config schema.
        assert ctx.tool_ctx.config is not None
        assert ctx.tool_ctx.config.active_domain == "research"
        assert ctx.tool_ctx.config.domain_overrides == {}
