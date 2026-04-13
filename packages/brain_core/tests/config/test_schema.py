from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.config.schema import Config, LLMConfig


def test_default_config_has_expected_defaults() -> None:
    c = Config()
    assert c.vault_path == Path.home() / "Documents" / "brain"
    assert c.active_domain == "research"
    assert c.autonomous_mode is False
    assert c.llm.provider == "anthropic"
    assert c.llm.default_model == "claude-sonnet-4-6"
    assert c.budget.daily_usd == 5.0
    assert c.budget.monthly_usd == 80.0
    assert c.web_port == 4317


def test_config_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError):
        Config(active_domain="marketing")  # type: ignore[arg-type]  # not in allowed set


def test_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        Config(active_doamin="research")  # type: ignore[call-arg]  # deliberate typo


def test_llm_config_model_change_roundtrips() -> None:
    cfg = LLMConfig(default_model="claude-haiku-4-5-20251001")
    assert cfg.default_model == "claude-haiku-4-5-20251001"
