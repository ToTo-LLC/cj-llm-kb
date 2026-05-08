"""Plan 17 Task 1 — brain_api production AnthropicProvider e2e integration test.

Plan 16 T31.5 + T39.5 wired the per-domain rate-limit gate end-to-end through
brain_api's lifespan, but coverage was unit + pin tests only — nothing
exercised the full ``brain_api → AnthropicProvider → Anthropic SDK`` path
against a real key. This module adds one network-bound integration test that
boots the production lifespan with a seeded ``config.json`` carrying a
per-domain rate-limit override, then drives ``brain_ping_llm`` three times
through the dispatcher to prove the wired path actually round-trips.

Skipped unless ``ANTHROPIC_API_KEY`` is set in the environment, so the brain
unit suite (and unprivileged CI runs without the secret) keep behaving
exactly as before — the test is invisible to anything but a CI job that
explicitly exports the secret to the environment.

Spec ambiguity flagged for the reviewer (Plan 17 T1):
    The spec proposes asserting on the per-domain leaky-bucket gate ("third
    call queues >25s OR returns 429"). However, ``brain_ping_llm``
    deliberately leaves ``LLMRequest.domain`` unset — see the Plan 16 T31.5
    adjudication in ``brain_core/tools/ping_llm.py:58-65`` — so the
    AnthropicProvider gate is a no-op for this tool regardless of any
    configured override. The spec's assertion shape is therefore not
    reachable through ``brain_ping_llm`` without modifying the tool itself,
    which is explicitly out of scope ("No changes to brain_ping_llm").
    This test instead pins what IS reachable end-to-end: the lifespan
    constructs an :class:`AnthropicProvider` with a live :class:`Config`
    containing a ``rate_limit_per_domain`` entry, and a real ``ping``
    round-trip completes successfully through that wired path. That's the
    full production wiring contract Plan 16 T39.5 introduced; the
    leaky-bucket gate itself is already pinned by the unit suite in
    ``brain_core/tests/llm/test_anthropic_rate_limit.py``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_api import create_app
from brain_core.config.schema import Config, ProviderConfig, RateLimitOverride
from brain_core.config.writer import save_config
from brain_core.llm.providers.anthropic import AnthropicProvider
from brain_core.llm.providers.anthropic import (
    _reset_buckets_for_tests as reset_anthropic_buckets,
)
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    "ANTHROPIC_API_KEY" not in os.environ,
    reason="Integration test requires ANTHROPIC_API_KEY env var.",
)


@pytest.fixture(autouse=True)
def _reset_buckets() -> Iterator[None]:
    """Clear the AnthropicProvider's module-level bucket registry around each test.

    The leaky-bucket registry in ``brain_core.llm.providers.anthropic`` is
    process-global, keyed on ``(domain, rpm)``. Without this guard, repeated
    runs of the e2e test (or sibling tests run in the same pytest process)
    would observe leaked bucket state — a test that filled the bucket
    couldn't drain it again from a clean baseline. ``autouse=True`` so every
    test in this module pays the (cheap) reset, both before AND after, so
    any other test that imports the provider also starts clean.
    """
    reset_anthropic_buckets()
    yield
    reset_anthropic_buckets()


def _seed_vault_with_rate_limit(vault_root: Path, *, domain: str, rpm: int) -> None:
    """Write ``<vault>/.brain/config.json`` with a per-domain rate-limit override.

    Mirrors the in-memory ``Config`` shape used by
    ``brain_core/tests/llm/test_anthropic_rate_limit.py::_build_config_with_rate_limit``
    but persists to disk so the lifespan's ``resolve_config`` (Plan 16 T34)
    picks it up exactly as a real install would.
    """
    config = Config(
        domains=[domain, "personal"],
        active_domain=domain,
        privacy_railed=["personal"],
        providers={
            "anthropic": ProviderConfig(
                rate_limit_per_domain={
                    domain: RateLimitOverride(requests_per_minute=rpm),
                },
            ),
        },
    )
    save_config(config, vault_root)


def test_brain_api_anthropic_e2e_round_trip(tmp_path: Path) -> None:
    """End-to-end: lifespan builds AnthropicProvider w/ rate-limit config, ping_llm round-trips.

    Seeds ``<vault>/.brain/config.json`` with
    ``providers.anthropic.rate_limit_per_domain = {"research": rpm=2}``,
    boots the brain_api lifespan (which constructs a real
    :class:`AnthropicProvider` because ``ANTHROPIC_API_KEY`` is set), and
    invokes ``brain_ping_llm`` three times through the dispatcher.

    Per the module docstring, the leaky-bucket gate is a no-op for
    ``brain_ping_llm`` (it leaves ``request.domain=None``), so the assertion
    shape is "all three calls succeed end-to-end" rather than "third call
    queues / 429s". The value of this test is proving the FULL production
    wiring path — ``create_app → _lifespan → resolve_config → AnthropicProvider →
    AsyncAnthropic SDK → live API → response`` — works against a real key.

    The provider identity check (``isinstance ctx.tool_ctx.llm,
    AnthropicProvider``) and the config-reference check
    (``provider._config is ctx.tool_ctx.config``) are duplicated from
    ``test_lifespan_anthropic_wiring.py`` deliberately: this test runs in a
    different env (real key vs. the dummy ``sk-test-not-real`` used by the
    pin test), so the symmetry of behavior is itself worth pinning.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault_with_rate_limit(vault, domain="research", rpm=2)

    app = create_app(
        vault_root=vault,
        allowed_domains=("research",),
        mount_static_ui=False,
    )

    # The Plan 17 T1 spec proposes ``timeout=60.0`` on the client; in
    # practice ``TestClient`` runs the ASGI app in-process and Starlette
    # explicitly deprecates passing ``timeout=`` to the underlying
    # ``client.post`` call (see starlette#1108) — the loopback transport
    # is synchronous so an httpx-level timeout is meaningless. The real
    # latency ceiling lives one layer down in
    # ``anthropic.AsyncAnthropic``, which carries its own default timeout
    # (60s as of SDK 0.40+). The CI step also has a wall-clock job
    # timeout, so a hung call surfaces as a step failure either way.
    with TestClient(app, base_url="http://localhost") as client:
        ctx = app.state.ctx

        # Lifespan-level identity checks: the provider IS the real one,
        # AND it carries the live Config reference (so the per-domain
        # rate-limit gate would actually fire IF the request carried a
        # domain). These are the same two invariants pinned by
        # ``test_lifespan_anthropic_wiring.test_lifespan_constructs_anthropic_provider_when_api_key_set``;
        # we re-pin under the real-key env to catch any regression that
        # only manifests when the SDK actually accepts the key.
        assert isinstance(ctx.tool_ctx.llm, AnthropicProvider)
        provider = ctx.tool_ctx.llm
        assert provider._config is ctx.tool_ctx.config
        # The override survived the persist + load round-trip.
        assert (
            ctx.tool_ctx.config.providers["anthropic"]
            .rate_limit_per_domain["research"]
            .requests_per_minute
            == 2
        )

        token = ctx.token
        headers = {
            "Origin": "http://localhost:4317",
            "X-Brain-Token": token,
        }

        # Three sequential ping_llm calls. Each is a 1-token round-trip
        # (max_tokens=1 in the tool's request). All three are expected
        # to return 200 + ok=True; per the docstring, the leaky-bucket
        # gate is a no-op for this tool because ``request.domain`` is
        # unset by ``ping_llm`` itself.
        for call_index in range(3):
            response = client.post(
                "/api/tools/brain_ping_llm",
                json={},
                headers=headers,
            )
            assert response.status_code == 200, (
                f"call {call_index}: HTTP {response.status_code} body={response.text!r}"
            )
            body = response.json()
            assert body["data"]["ok"] is True, (
                f"call {call_index}: ping_llm reported ok=False: {body!r}"
            )
            assert body["data"]["provider"] == "anthropic"
            # ``model`` echoes whatever the SDK returned, which is the
            # configured model with date stamp baked in by Anthropic.
            # Just assert it's a non-empty string — pinning a specific
            # date stamp would make the test fragile to model rotations.
            assert isinstance(body["data"]["model"], str)
            assert body["data"]["model"]
            # Latency is recorded; 1-token round-trips are typically
            # <2000ms but we leave plenty of headroom (network jitter,
            # cold caches). The point of asserting the field is to
            # prove the latency-recording code path didn't regress.
            assert isinstance(body["data"]["latency_ms"], int)
            assert body["data"]["latency_ms"] >= 0
