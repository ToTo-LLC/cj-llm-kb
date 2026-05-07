"""Plan 16 Task 39.5 — brain_api lifespan AnthropicProvider wiring.

Pins two properties of the lifespan's LLM-provider construction:

1. ``ANTHROPIC_API_KEY`` UNSET → ``ctx.tool_ctx.llm`` is a ``FakeLLMProvider``.
   Existing tests run without the env var; they keep getting the no-network
   stub via ``build_app_context``'s ``llm or FakeLLMProvider()`` default.

2. ``ANTHROPIC_API_KEY`` SET → ``ctx.tool_ctx.llm`` is an ``AnthropicProvider``
   AND it carries the resolved ``Config`` reference (so its T31 per-domain
   rate-limit gate fires end-to-end).

Without this wiring, every brain_api instance ran ``FakeLLMProvider`` —
brain_web users got scripted fake responses in production. The fix mirrors
the analog wiring in ``brain_cli/session_factory.py`` (T31.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.providers.anthropic import AnthropicProvider
from fastapi.testclient import TestClient


def test_lifespan_uses_fake_llm_when_api_key_unset(
    seeded_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``ANTHROPIC_API_KEY`` → FakeLLMProvider on the embedded ToolContext.

    The pre-existing brain_api test suite relies on this — none of the
    fixtures set ``ANTHROPIC_API_KEY`` and a regression that constructed
    a real provider on every boot would attempt outbound network calls
    in CI. Pin the no-key fall-back explicitly.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/healthz").status_code == 200
        ctx = app.state.ctx
        assert isinstance(ctx.tool_ctx.llm, FakeLLMProvider)


def test_lifespan_constructs_anthropic_provider_when_api_key_set(
    seeded_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ANTHROPIC_API_KEY`` set → AnthropicProvider with the live Config.

    Identity check on ``provider._config is ctx.tool_ctx.config`` is
    load-bearing: the T31 per-domain rate-limit gate reads
    ``self._config.providers["anthropic"].rate_limit_per_domain`` at
    request time. Without the same Config reference, an in-flight
    ``brain_config_set`` mutation that updates the rate limit would
    not be visible to the provider — defeating the whole point of
    threading Config through.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    app = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/healthz").status_code == 200
        ctx = app.state.ctx
        assert isinstance(ctx.tool_ctx.llm, AnthropicProvider)
        # Same Config reference — not a model_copy.
        # ``provider._config`` is the field T31 reads at request time.
        provider = ctx.tool_ctx.llm
        assert provider._config is ctx.tool_ctx.config
