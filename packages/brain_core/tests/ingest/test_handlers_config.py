"""Tests for issue #23 — per-handler tunables wired through Config.

The user-facing surface is:
1. ``HandlersConfig`` (pydantic schema) holds per-handler sub-configs with
   sensible defaults that match the previous hardcoded constants.
2. ``URLHandler``/``TweetHandler``/``PDFHandler`` accept their tunables in
   the constructor (kw-only) and default to the same hardcoded values, so
   ``URLHandler()`` (no-config) keeps pre-issue-#23 behavior bit-for-bit.
3. ``_default_handlers(cfg)`` applies the overrides from ``cfg`` to the
   relevant handlers; ``_default_handlers(None)`` is identical to the
   pre-issue-#23 ``_default_handlers()``.
4. ``IngestPipeline.handlers`` is an optional field; when set, ``ingest()``
   threads it through ``dispatch(...)``.
5. The MCP-tool layer (``brain_core.tools.ingest._build_pipeline_from_ctx``
   and ``brain_core.tools.bulk_import._build_pipeline``) build the handler
   list from ``ctx.config.handlers`` when a config is wired.
"""

from __future__ import annotations

from brain_core.config.schema import (
    HandlersConfig,
    PDFHandlerConfig,
    TweetHandlerConfig,
    URLHandlerConfig,
)
from brain_core.ingest.dispatcher import _default_handlers
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler


# ---------------------------------------------------------------------------
# Schema defaults — must match the previously-hardcoded handler constants
# ---------------------------------------------------------------------------


def test_url_handler_config_default_matches_legacy_hardcoded_30() -> None:
    """The default must equal the value that lived in url.py before #23."""
    assert URLHandlerConfig().timeout_seconds == 30.0


def test_tweet_handler_config_default_matches_legacy_hardcoded_20() -> None:
    """The default must equal the value that lived in tweet.py before #23."""
    assert TweetHandlerConfig().timeout_seconds == 20.0


def test_pdf_handler_config_default_matches_legacy_hardcoded_200() -> None:
    """The default must equal the value that lived in pdf.py before #23."""
    assert PDFHandlerConfig().min_chars == 200


def test_handlers_config_defaults_are_legacy_values() -> None:
    """Composite default — sanity check that the aggregate config defaults
    don't drift from the per-handler defaults."""
    cfg = HandlersConfig()
    assert cfg.url.timeout_seconds == 30.0
    assert cfg.tweet.timeout_seconds == 20.0
    assert cfg.pdf.min_chars == 200


def test_handlers_config_rejects_zero_or_negative_timeout() -> None:
    """Pydantic ``gt=0`` constraint on timeouts."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        URLHandlerConfig(timeout_seconds=0)
    with pytest.raises(ValidationError):
        URLHandlerConfig(timeout_seconds=-1)
    with pytest.raises(ValidationError):
        TweetHandlerConfig(timeout_seconds=0)


def test_handlers_config_rejects_negative_min_chars() -> None:
    """Pydantic ``ge=0`` constraint on min_chars (zero is OK = disable check)."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PDFHandlerConfig(min_chars=-1)
    # Zero must be allowed — disables the scanned-PDF check.
    assert PDFHandlerConfig(min_chars=0).min_chars == 0


# ---------------------------------------------------------------------------
# Handler constructors honor the tunables
# ---------------------------------------------------------------------------


def test_url_handler_default_timeout_matches_legacy() -> None:
    """``URLHandler()`` with no constructor arg keeps the pre-#23 timeout."""
    assert URLHandler()._timeout_seconds == 30.0  # type: ignore[attr-defined]


def test_url_handler_honors_timeout_override() -> None:
    assert URLHandler(timeout_seconds=5.0)._timeout_seconds == 5.0  # type: ignore[attr-defined]


def test_tweet_handler_default_timeout_matches_legacy() -> None:
    assert TweetHandler()._timeout_seconds == 20.0  # type: ignore[attr-defined]


def test_tweet_handler_honors_timeout_override() -> None:
    assert TweetHandler(timeout_seconds=2.5)._timeout_seconds == 2.5  # type: ignore[attr-defined]


def test_pdf_handler_honors_min_chars_override() -> None:
    """PDFHandler already exposed min_chars before #23 — pin it."""
    assert PDFHandler(min_chars=50)._min_chars == 50  # type: ignore[attr-defined]
    assert PDFHandler()._min_chars == 200  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _default_handlers applies the config
# ---------------------------------------------------------------------------


def _find(handlers: list[object], cls: type) -> object:
    for h in handlers:
        if isinstance(h, cls):
            return h
    raise AssertionError(f"no {cls.__name__} in {handlers!r}")


def test_default_handlers_with_no_config_uses_legacy_defaults() -> None:
    """Pre-#23 behavior: ``_default_handlers()`` (no arg / None) builds
    handlers with the hardcoded defaults."""
    handlers = _default_handlers()
    url_h = _find(handlers, URLHandler)
    tweet_h = _find(handlers, TweetHandler)
    pdf_h = _find(handlers, PDFHandler)
    assert url_h._timeout_seconds == 30.0  # type: ignore[attr-defined]
    assert tweet_h._timeout_seconds == 20.0  # type: ignore[attr-defined]
    assert pdf_h._min_chars == 200  # type: ignore[attr-defined]


def test_default_handlers_with_config_applies_overrides() -> None:
    """Issue #23 — supplied config flows into the relevant handlers."""
    cfg = HandlersConfig(
        url=URLHandlerConfig(timeout_seconds=7.5),
        tweet=TweetHandlerConfig(timeout_seconds=3.0),
        pdf=PDFHandlerConfig(min_chars=42),
    )
    handlers = _default_handlers(cfg)
    url_h = _find(handlers, URLHandler)
    tweet_h = _find(handlers, TweetHandler)
    pdf_h = _find(handlers, PDFHandler)
    assert url_h._timeout_seconds == 7.5  # type: ignore[attr-defined]
    assert tweet_h._timeout_seconds == 3.0  # type: ignore[attr-defined]
    assert pdf_h._min_chars == 42  # type: ignore[attr-defined]


def test_default_handlers_preserves_order_with_config() -> None:
    """The whole point of ``_default_handlers`` is the careful ordering;
    the config-aware variant must NOT reorder.
    """
    no_cfg_types = [type(h) for h in _default_handlers()]
    cfg_types = [type(h) for h in _default_handlers(HandlersConfig())]
    assert no_cfg_types == cfg_types


# ---------------------------------------------------------------------------
# IngestPipeline.handlers field threads through
# ---------------------------------------------------------------------------


def test_ingest_pipeline_handlers_field_defaults_to_none() -> None:
    """Source-compat: every existing pipeline construction site that doesn't
    set ``handlers=...`` keeps working unchanged."""
    from pathlib import Path

    from brain_core.ingest.pipeline import IngestPipeline
    from brain_core.llm.fake import FakeLLMProvider
    from brain_core.vault.writer import VaultWriter

    p = IngestPipeline(
        vault_root=Path("/tmp/x"),
        writer=VaultWriter(vault_root=Path("/tmp/x")),
        llm=FakeLLMProvider(),
        summarize_model="m",
        integrate_model="m",
        classify_model="m",
    )
    assert p.handlers is None


def test_ingest_pipeline_handlers_field_accepts_custom_list() -> None:
    """Pipeline accepts a config-resolved handler list (issue #23)."""
    from pathlib import Path

    from brain_core.ingest.pipeline import IngestPipeline
    from brain_core.llm.fake import FakeLLMProvider
    from brain_core.vault.writer import VaultWriter

    cfg = HandlersConfig(url=URLHandlerConfig(timeout_seconds=11.0))
    handlers = _default_handlers(cfg)
    p = IngestPipeline(
        vault_root=Path("/tmp/x"),
        writer=VaultWriter(vault_root=Path("/tmp/x")),
        llm=FakeLLMProvider(),
        summarize_model="m",
        integrate_model="m",
        classify_model="m",
        handlers=handlers,
    )
    assert p.handlers is handlers
    url_h = _find(p.handlers, URLHandler)
    assert url_h._timeout_seconds == 11.0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# MCP-tool layer reads ctx.config.handlers
# ---------------------------------------------------------------------------


def test_build_pipeline_from_ctx_uses_config_handlers() -> None:
    """``brain_core.tools.ingest._build_pipeline_from_ctx`` resolves the
    handler list from ``ctx.config.handlers`` when a config is wired."""
    from dataclasses import replace
    from pathlib import Path

    from brain_core.config.schema import Config
    from brain_core.llm.fake import FakeLLMProvider
    from brain_core.tools.base import ToolContext
    from brain_core.tools.ingest import _build_pipeline_from_ctx
    from brain_core.vault.writer import VaultWriter

    vault = Path("/tmp/v23")
    base = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=VaultWriter(vault_root=vault),
        llm=FakeLLMProvider(),
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    cfg = Config()
    cfg = cfg.model_copy(
        update={
            "handlers": HandlersConfig(
                url=URLHandlerConfig(timeout_seconds=4.0),
                pdf=PDFHandlerConfig(min_chars=99),
            )
        }
    )
    ctx = replace(base, config=cfg)
    # Plan 11 D8: ``_build_pipeline_from_ctx`` now requires an explicit
    # ``domain``. ``None`` matches the legacy auto-detect path tested here.
    pipeline = _build_pipeline_from_ctx(ctx, domain=None)
    assert pipeline.handlers is not None, (
        "tool layer must build a handler list when config is supplied"
    )
    url_h = _find(pipeline.handlers, URLHandler)
    pdf_h = _find(pipeline.handlers, PDFHandler)
    assert url_h._timeout_seconds == 4.0  # type: ignore[attr-defined]
    assert pdf_h._min_chars == 99  # type: ignore[attr-defined]


def test_build_pipeline_from_ctx_no_config_passes_none_handlers() -> None:
    """No config → ``handlers=None`` so the dispatcher uses legacy defaults.

    Pins the source-compat contract for the 56+ ToolContext construction
    sites that don't supply a config.
    """
    from pathlib import Path

    from brain_core.llm.fake import FakeLLMProvider
    from brain_core.tools.base import ToolContext
    from brain_core.tools.ingest import _build_pipeline_from_ctx
    from brain_core.vault.writer import VaultWriter

    vault = Path("/tmp/v23-noconfig")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=VaultWriter(vault_root=vault),
        llm=FakeLLMProvider(),
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    assert ctx.config is None  # sanity
    # Plan 11 D8: ``_build_pipeline_from_ctx`` now requires an explicit
    # ``domain``. ``None`` matches the legacy auto-detect path tested here.
    pipeline = _build_pipeline_from_ctx(ctx, domain=None)
    assert pipeline.handlers is None
