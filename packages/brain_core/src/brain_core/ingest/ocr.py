"""OCR helper — runs an image through ``LLMProvider.vision_extract`` and
records cost via the standard ledger / budget rails.

Plan 24 Task 3 / D4: this module is the single seam between the
DocxHandler / PptxHandler image-extract output (``extras["images"]``)
and the LLMProvider abstraction. T4 will call :func:`ocr_image` from
the ingest pipeline's post-extract OCR pass.

Architectural notes:

* Imports :class:`LLMProvider` from :mod:`brain_core.llm` (the
  Protocol), NOT a concrete SDK. Honors CLAUDE.md non-negotiable #4.
* Records a ledger row with ``operation="ocr"`` per Plan 24 D6. The
  cost ledger accepts arbitrary operation strings (free-form column,
  not an enum), so no schema change is needed — just a new tag the
  cost rollups will surface under ``by_operation`` once we wire it.
* Budget rail: caller passes a :class:`PerDomainBudgetGuard` +
  :class:`Config`; this helper invokes ``guard.check_for(domain,
  config)`` BEFORE the LLM call. Budget exhaustion raises
  :class:`BudgetCapExceeded` (uncaught) so the pipeline aborts the
  OCR pass cleanly. Global :class:`BudgetEnforcer` is intentionally
  NOT wired here — the pipeline's outer call site already gates the
  global cap once per ingest run; layering it on each per-image call
  would double-count projected spend.
* Cost computation: uses :meth:`BudgetEnforcer.estimate_cost` with the
  graceful-degradation pattern from
  :func:`brain_core.ingest.pipeline._estimate_call_cost` — unknown
  models degrade to ``0.0`` so a test stub model doesn't crash the
  pipeline.

The default prompt is intentionally tight: "Extract any text visible
in this image. Return only the text, with no commentary." Variations
(e.g., "describe this chart") are out of scope for v1; T4 calls
:func:`ocr_image` with the default prompt and adds the result as
``[Image: <text>]`` blocks in the body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from brain_core.cost.budget import BudgetEnforcer
from brain_core.cost.ledger import CostEntry

if TYPE_CHECKING:
    from brain_core.budget import PerDomainBudgetGuard
    from brain_core.config.schema import Config
    from brain_core.cost.ledger import CostLedger
    from brain_core.llm.provider import LLMProvider


DEFAULT_OCR_PROMPT = (
    "Extract any text visible in this image. "
    "Return only the text, with no commentary."
)

# Plan 24 Task 3 / D6: the ledger-row operation tag for Claude Vision
# OCR calls. Centralized as a constant so the pipeline + tests + future
# cost-rollup queries can reference the same string.
OCR_OPERATION = "ocr"


@dataclass(frozen=True)
class OCRResult:
    """Typed output of :func:`ocr_image`.

    ``text`` is the extracted text (may be empty if the image has no
    legible text). ``cost_usd`` is the recorded cost (0.0 when the
    model isn't in the pricing table). ``model`` is the actual model
    used (resolves the caller's optional override against the
    provider's default).
    """

    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


async def ocr_image(
    *,
    image_bytes: bytes,
    content_type: str,
    domain: str,
    llm_provider: LLMProvider,
    cost_ledger: CostLedger,
    budget_guard: PerDomainBudgetGuard,
    config: Config,
    prompt: str = DEFAULT_OCR_PROMPT,
    model: str | None = None,
) -> OCRResult:
    """Run one image through Claude Vision and record a ledger row.

    Order of operations:

    1. ``budget_guard.check_for(domain, config)`` — raise
       :class:`BudgetCapExceeded` if the per-domain cap is exhausted.
    2. ``llm_provider.vision_extract(image_bytes, prompt, ...)`` — run
       the upstream call.
    3. Compute cost via :meth:`BudgetEnforcer.estimate_cost`. Unknown
       model -> 0.0 (graceful degradation; test stubs use fake model
       strings).
    4. Record a :class:`CostEntry` with ``operation="ocr"``.
    5. Return :class:`OCRResult` so the caller can inline the
       extracted text into the body.

    The caller is responsible for chunking ``extras["images"]`` and
    catching :class:`BudgetCapExceeded` if it wants partial-success
    semantics (abort-on-first-budget-breach is the default).
    """
    budget_guard.check_for(domain=domain, config=config)

    text, input_tokens, output_tokens = await llm_provider.vision_extract(
        image_bytes,
        prompt,
        content_type=content_type,
        model=model,
    )

    # Resolve the effective model string: caller's override wins, else
    # ask the provider what default it used by trusting our local
    # default constant. The provider doesn't echo back the resolved
    # model from ``vision_extract`` (return shape is just text+tokens)
    # so we mirror the same resolution logic the AnthropicProvider does.
    resolved_model = model or _default_vision_model()

    try:
        cost_usd = BudgetEnforcer.estimate_cost(
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except KeyError:
        cost_usd = 0.0

    cost_ledger.record(
        CostEntry(
            timestamp=datetime.now(tz=UTC),
            operation=OCR_OPERATION,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            domain=domain,
        )
    )

    return OCRResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        model=resolved_model,
    )


def _default_vision_model() -> str:
    """Return the default vision model string.

    Indirected through a function so a future Config field
    (``LLMConfig.vision_model``) can replace this constant without
    touching the helper's signature. Currently mirrors the constant in
    :mod:`brain_core.llm.providers.anthropic` — keeping the two in
    sync is the lightest-weight option until a real config seam lands.
    """
    return "claude-sonnet-4-6"
