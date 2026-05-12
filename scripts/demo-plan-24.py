#!/usr/bin/env python3
"""Plan 24 end-to-end demo — DOCX + PPTX ingest with Claude Vision OCR closure.

Walks every substantive-task gate from
``tasks/plans/24-docx-pptx-ingest.md`` (T0 → T5.5) plus the closure
marker. Each gate is a structural assertion (file existence, regex
match, ``inspect.signature`` / Pydantic-introspection check, source
text pin) — no live LLM, no network, no spawned servers. Mirrors the
demo-plan-22 / demo-plan-23 shape (cached file reads, single-purpose
gate functions, fail-fast main loop).

Gate map
--------
 1   T0.a  Spec §5 handlers table contains ``docx`` + ``pptx`` rows.
 2   T0.b  Spec §5 contains "Image OCR rules" subsection.
 3   T0.c  Spec §10 contains the "Vision OCR cost metering" bullet.
 4   T0.d  ``SourceType`` enum has ``DOCX`` + ``PPTX`` members
            (introspection check via Pydantic enum import).
 5   T1    ``packages/brain_core/.../handlers/docx.py`` exists with
            ``DocxHandler``; dispatcher registers DocxHandler AFTER
            TranscriptDOCXHandler in ``_default_handlers()``.
 6   T1.5  ``TranscriptDOCXHandler.can_handle`` content-sniffs via
            regex patterns (speaker / bracket-speaker / timestamp /
            arrow patterns + ``_TRANSCRIPT_MIN_MATCHES`` threshold).
 7   T2    ``packages/brain_core/.../handlers/pptx.py`` exists with
            ``PptxHandler``; ``python-pptx>=0.6`` declared in
            ``packages/brain_core/pyproject.toml``; dispatcher
            registers PptxHandler.
 8   T3.a  ``LLMProvider`` Protocol has ``vision_extract`` method
            (``inspect.signature`` check on the protocol class).
 9   T3.b  ``AnthropicProvider`` implements ``vision_extract`` as a
            concrete method on the class.
10   T3.c  ``brain_core.ingest.ocr`` module exposes ``ocr_image``
            helper + ``OCR_OPERATION = "ocr"`` constant.
11   T4.a  ``pipeline.py`` ``ingest()`` runs an OCR pass via
            ``self._ocr_images(...)`` + ``ocr_image`` is imported.
12   T4.b  OCR inline format follows ``[Image: ...]`` (docx) +
            ``[Image (slide N): ...]`` (pptx) patterns.
13   T5    Drop-zone accept list (``INGEST_ACCEPT``) declares both
            Office Open XML MIME types in ``inbox-store.ts``;
            source-row ``TypeIcon`` switch has ``docx`` + ``pptx``
            cases.
14   T5.5  ``inbox-store.ts`` reads ``source_type`` from the
            ``recentIngests`` response AND ``drop-zone.tsx`` defines
            ``inferIngestTypeFromFilename`` (extension-sniff for
            optimistic rows).
15   T6    ``tasks/todo.md`` row 24 ✅ + ``tasks/lessons.md`` has a
            ``## Plan 24`` closure section.

Closure (T6) is this script; final stdout line on a clean run is
``PLAN 24 DEMO OK``.

Per Plan 24 plan-doc §"Demo gate description": "~10-12 gates". This
script lands 15 gates — 1 per T0 sub-step (4), 1 per substantive
task (T1, T1.5, T2, T3.a/b/c — split for the 3 surfaces, T4.a/b — split
for code + format, T5, T5.5) + 1 closure. Matches the plan-doc gate
list with the T0 / T3 / T4 / T5 splits the spec calls out explicitly.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_CORE = _REPO_ROOT / "packages" / "brain_core"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"

_SPEC = (
    _REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-04-13-cj-llm-kb-design.md"
)
_TYPES = _BRAIN_CORE / "src" / "brain_core" / "ingest" / "types.py"
_DOCX_HANDLER = (
    _BRAIN_CORE / "src" / "brain_core" / "ingest" / "handlers" / "docx.py"
)
_PPTX_HANDLER = (
    _BRAIN_CORE / "src" / "brain_core" / "ingest" / "handlers" / "pptx.py"
)
_TRANSCRIPT_DOCX_HANDLER = (
    _BRAIN_CORE
    / "src"
    / "brain_core"
    / "ingest"
    / "handlers"
    / "transcript_docx.py"
)
_DISPATCHER = (
    _BRAIN_CORE / "src" / "brain_core" / "ingest" / "dispatcher.py"
)
_PIPELINE = _BRAIN_CORE / "src" / "brain_core" / "ingest" / "pipeline.py"
_OCR = _BRAIN_CORE / "src" / "brain_core" / "ingest" / "ocr.py"
_LLM_PROVIDER = _BRAIN_CORE / "src" / "brain_core" / "llm" / "provider.py"
_LLM_ANTHROPIC = (
    _BRAIN_CORE / "src" / "brain_core" / "llm" / "providers" / "anthropic.py"
)
_BRAIN_CORE_PYPROJECT = _BRAIN_CORE / "pyproject.toml"

_INBOX_STORE = _BRAIN_WEB / "src" / "lib" / "state" / "inbox-store.ts"
_SOURCE_ROW = (
    _BRAIN_WEB / "src" / "components" / "inbox" / "source-row.tsx"
)
_DROP_ZONE = _BRAIN_WEB / "src" / "components" / "inbox" / "drop-zone.tsx"

_TODO = _REPO_ROOT / "tasks" / "todo.md"
_LESSONS = _REPO_ROOT / "tasks" / "lessons.md"


def _gate(label: str) -> None:
    print(f"  ok Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  FAIL Gate {label}: {why}", file=sys.stderr)
    return 1


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exists(label: str, path: Path) -> int:
    if not path.is_file():
        return _fail(label, f"file missing: {path}")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — T0.a: spec §5 handlers table contains docx + pptx rows.
# ---------------------------------------------------------------------------


def _gate_1_t0_spec_handlers_table() -> int:
    if rc := _exists("1", _SPEC):
        return rc
    text = _read(_SPEC)
    # docx row — leading pipe + name + python-docx (existing); the row
    # references TranscriptDOCXHandler claim-order contract from D3.
    if not re.search(
        r"\|\s*docx\s*\|\s*`python-docx`",
        text,
    ):
        return _fail(
            "1",
            "spec §5 handlers table missing `| docx | \\`python-docx\\` ...` row",
        )
    # pptx row — leading pipe + name + python-pptx NEW dep marker.
    if not re.search(
        r"\|\s*pptx\s*\|\s*`python-pptx",
        text,
    ):
        return _fail(
            "1",
            "spec §5 handlers table missing `| pptx | \\`python-pptx ...` row",
        )
    _gate(
        "1 — T0.a spec §5 handlers table: docx + pptx rows landed "
        "with python-docx / python-pptx library refs"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T0.b: spec §5 contains "Image OCR rules" subsection.
# ---------------------------------------------------------------------------


def _gate_2_t0_spec_ocr_rules() -> int:
    text = _read(_SPEC)
    # Heading literal — markdown level varies (### per plan-doc); regex
    # accepts ## or ### so a level bump doesn't fail RED here.
    if not re.search(r"^#{2,4}\s+Image\s+OCR\s+rules\s*$", text, re.MULTILINE):
        return _fail(
            "2",
            "spec §5 missing `### Image OCR rules` subsection heading",
        )
    # The subsection body must reference vision_extract + the per-image
    # block format (D5 always-OCR + the [Image: ...] / [Image (slide N): ...]
    # inline marker introduced in T4).
    if "vision_extract" not in text:
        return _fail(
            "2",
            "spec §5 Image OCR rules subsection missing `vision_extract` reference",
        )
    if not re.search(r"\[Image\s*:", text):
        return _fail(
            "2",
            "spec §5 Image OCR rules subsection missing `[Image: ...]` block format",
        )
    _gate(
        "2 — T0.b spec §5 Image OCR rules subsection: heading + "
        "vision_extract + [Image: ...] block format all present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T0.c: spec §10 vision-cost-metering bullet.
# ---------------------------------------------------------------------------


def _gate_3_t0_spec_vision_cost_bullet() -> int:
    text = _read(_SPEC)
    # The bullet literal — heading + "Vision OCR cost metering" + op="ocr"
    # + PerDomainBudgetGuard reference (D6 cost-rail integration).
    if "Vision OCR cost metering" not in text:
        return _fail(
            "3",
            "spec §10 missing `Vision OCR cost metering` bullet text",
        )
    # The bullet must reference op="ocr" so the ledger-row tag contract
    # is pinned at the spec level (D6).
    if not re.search(r'op\s*=\s*[\'"]ocr[\'"]', text):
        return _fail(
            "3",
            'spec §10 vision-cost-metering bullet missing `op="ocr"` reference',
        )
    # The same bullet must reference PerDomainBudgetGuard so the
    # budget-rail integration contract is pinned at the spec level.
    if "PerDomainBudgetGuard" not in text:
        return _fail(
            "3",
            "spec §10 vision-cost-metering bullet missing "
            "`PerDomainBudgetGuard` reference",
        )
    _gate(
        "3 — T0.c spec §10 vision-cost-metering: bullet text + "
        'op="ocr" + PerDomainBudgetGuard all present'
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T0.d: SourceType enum has DOCX + PPTX members.
# ---------------------------------------------------------------------------


def _gate_4_t0_source_type_enum() -> int:
    if rc := _exists("4", _TYPES):
        return rc
    # Direct enum introspection — fail RED if either member is removed
    # or renamed. Importing via PYTHONPATH (set by the demo recipe) so
    # this runs cleanly under the uv-bypass recipe.
    try:
        from brain_core.ingest.types import SourceType  # type: ignore[import-not-found]  # noqa: E501
    except ImportError as exc:
        return _fail(
            "4",
            f"could not import brain_core.ingest.SourceType: {exc}",
        )
    members = set(SourceType.__members__.keys())
    if "DOCX" not in members:
        return _fail(
            "4",
            f"SourceType missing `DOCX` member; got {sorted(members)}",
        )
    if "PPTX" not in members:
        return _fail(
            "4",
            f"SourceType missing `PPTX` member; got {sorted(members)}",
        )
    # String-value pin so a rename (e.g. DOCX = "word_doc") fails RED.
    if SourceType.DOCX.value != "docx":
        return _fail(
            "4",
            f'SourceType.DOCX.value must be "docx"; got '
            f'{SourceType.DOCX.value!r}',
        )
    if SourceType.PPTX.value != "pptx":
        return _fail(
            "4",
            f'SourceType.PPTX.value must be "pptx"; got '
            f'{SourceType.PPTX.value!r}',
        )
    _gate(
        "4 — T0.d SourceType enum: DOCX + PPTX members present with "
        'canonical "docx" / "pptx" string values'
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T1: DocxHandler exists; dispatcher registers it AFTER
# TranscriptDOCXHandler.
# ---------------------------------------------------------------------------


def _gate_5_t1_docx_handler_and_registration() -> int:
    if rc := _exists("5", _DOCX_HANDLER):
        return rc
    docx_text = _read(_DOCX_HANDLER)
    if not re.search(r"^class\s+DocxHandler\b", docx_text, re.MULTILINE):
        return _fail(
            "5",
            "handlers/docx.py missing `class DocxHandler` definition",
        )
    if rc := _exists("5", _DISPATCHER):
        return rc
    disp_text = _read(_DISPATCHER)
    # The dispatcher must import BOTH handler classes (TranscriptDOCXHandler
    # was pre-existing; DocxHandler is the Plan 24 addition).
    if "TranscriptDOCXHandler" not in disp_text:
        return _fail(
            "5",
            "dispatcher.py missing `TranscriptDOCXHandler` import",
        )
    if "DocxHandler" not in disp_text:
        return _fail("5", "dispatcher.py missing `DocxHandler` import")
    # Per D3: DocxHandler MUST be registered AFTER TranscriptDOCXHandler
    # inside _default_handlers(). Extract the function body and verify
    # ordering by index.
    body_match = re.search(
        r"def\s+_default_handlers\s*\([^)]*\)[^:]*:\s*\n"
        r"(.+?)(?=\n(?:def |class |async def )|\Z)",
        disp_text,
        re.DOTALL,
    )
    if body_match is None:
        return _fail(
            "5",
            "dispatcher.py missing `_default_handlers` function",
        )
    body = body_match.group(1)
    transcript_idx = body.find("TranscriptDOCXHandler(")
    docx_idx = body.find("DocxHandler(")
    if transcript_idx < 0:
        return _fail(
            "5",
            "_default_handlers() missing `TranscriptDOCXHandler()` instance",
        )
    if docx_idx < 0:
        return _fail(
            "5",
            "_default_handlers() missing `DocxHandler()` instance",
        )
    if docx_idx <= transcript_idx:
        return _fail(
            "5",
            "_default_handlers(): DocxHandler() must be registered AFTER "
            "TranscriptDOCXHandler() (Plan 24 D3 claim-order contract)",
        )
    _gate(
        "5 — T1 DocxHandler: class defined + dispatcher registers "
        "DocxHandler AFTER TranscriptDOCXHandler (D3 honored)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T1.5: TranscriptDOCXHandler.can_handle content-sniffs.
# ---------------------------------------------------------------------------


def _gate_6_t1_5_content_sniff() -> int:
    if rc := _exists("6", _TRANSCRIPT_DOCX_HANDLER):
        return rc
    text = _read(_TRANSCRIPT_DOCX_HANDLER)
    # Pre-T1.5 the handler claimed any `.docx` by suffix; T1.5 added 4
    # regex patterns + a min-matches threshold for content-sniffing.
    # Pin all 4 pattern names + the threshold constant.
    for name in (
        "_SPEAKER_PATTERN",
        "_BRACKET_SPEAKER_PATTERN",
        "_TIMESTAMP_PATTERN",
        "_ARROW_SPEAKER_PATTERN",
        "_TRANSCRIPT_MIN_MATCHES",
    ):
        if name not in text:
            return _fail(
                "6",
                f"transcript_docx.py missing `{name}` (Plan 24 T1.5 "
                "content-sniff contract)",
            )
    # The `can_handle` method must actually consume the patterns — not
    # just declare them. Pin a regex-match call inside the function
    # body so a regression that re-introduces suffix-only claim fails RED.
    can_handle_match = re.search(
        r"def\s+can_handle\s*\([^)]*\)[^:]*:\s*\n(.+?)(?=\n(?:    def |"
        r"class |def |async def )|\Z)",
        text,
        re.DOTALL,
    )
    if can_handle_match is None:
        return _fail(
            "6",
            "transcript_docx.py missing `can_handle` method body",
        )
    can_handle_body = can_handle_match.group(1)
    if "_TRANSCRIPT_MIN_MATCHES" not in can_handle_body:
        return _fail(
            "6",
            "transcript_docx.can_handle does not reference "
            "_TRANSCRIPT_MIN_MATCHES — content-sniff threshold not "
            "applied (Plan 24 T1.5)",
        )
    _gate(
        "6 — T1.5 content-sniff: 4 regex patterns + "
        "_TRANSCRIPT_MIN_MATCHES threshold + can_handle consumes them"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T2: PptxHandler exists + python-pptx dep + dispatcher registers.
# ---------------------------------------------------------------------------


def _gate_7_t2_pptx_handler_and_dep() -> int:
    if rc := _exists("7", _PPTX_HANDLER):
        return rc
    pptx_text = _read(_PPTX_HANDLER)
    if not re.search(r"^class\s+PptxHandler\b", pptx_text, re.MULTILINE):
        return _fail(
            "7",
            "handlers/pptx.py missing `class PptxHandler` definition",
        )
    if rc := _exists("7", _BRAIN_CORE_PYPROJECT):
        return rc
    pyproject_text = _read(_BRAIN_CORE_PYPROJECT)
    # D12: `python-pptx>=0.6` declared in brain_core/pyproject.toml.
    if not re.search(r'["\']python-pptx>=0\.6', pyproject_text):
        return _fail(
            "7",
            "brain_core/pyproject.toml missing `python-pptx>=0.6` "
            "declaration (Plan 24 D12 first new pip dep since Plan 16 "
            "watchdog)",
        )
    disp_text = _read(_DISPATCHER)
    if "PptxHandler" not in disp_text:
        return _fail("7", "dispatcher.py missing `PptxHandler` import")
    # The dispatcher must register PptxHandler inside _default_handlers().
    body_match = re.search(
        r"def\s+_default_handlers\s*\([^)]*\)[^:]*:\s*\n"
        r"(.+?)(?=\n(?:def |class |async def )|\Z)",
        disp_text,
        re.DOTALL,
    )
    if body_match is None or "PptxHandler(" not in body_match.group(1):
        return _fail(
            "7",
            "_default_handlers() missing `PptxHandler()` instance",
        )
    _gate(
        "7 — T2 PptxHandler: class defined + python-pptx>=0.6 in "
        "brain_core pyproject + dispatcher registers PptxHandler()"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T3.a: LLMProvider Protocol has vision_extract method.
# ---------------------------------------------------------------------------


def _gate_8_t3_llm_provider_vision_extract() -> int:
    if rc := _exists("8", _LLM_PROVIDER):
        return rc
    try:
        from brain_core.llm.provider import LLMProvider  # type: ignore[import-not-found]  # noqa: E501
    except ImportError as exc:
        return _fail(
            "8",
            f"could not import brain_core.llm.LLMProvider: {exc}",
        )
    # vision_extract MUST be defined on the Protocol — not on a
    # concrete provider subclass. ``inspect.signature`` raises if the
    # attribute isn't callable; the call also surfaces a real signature
    # mismatch (e.g. if vision_extract was added without the required
    # image_bytes argument).
    if not hasattr(LLMProvider, "vision_extract"):
        return _fail(
            "8",
            "LLMProvider Protocol missing `vision_extract` method "
            "(CLAUDE.md non-negotiable #4: LLM-touching code goes "
            "through the abstraction, not anthropic SDK directly)",
        )
    sig = inspect.signature(LLMProvider.vision_extract)  # type: ignore[arg-type]
    params = sig.parameters
    if "image_bytes" not in params:
        return _fail(
            "8",
            f"LLMProvider.vision_extract signature missing "
            f"`image_bytes` parameter; got {list(params)}",
        )
    if "prompt" not in params:
        return _fail(
            "8",
            f"LLMProvider.vision_extract signature missing `prompt` "
            f"parameter; got {list(params)}",
        )
    _gate(
        "8 — T3.a LLMProvider.vision_extract: method on Protocol + "
        "image_bytes + prompt parameters present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T3.b: AnthropicProvider implements vision_extract.
# ---------------------------------------------------------------------------


def _gate_9_t3_anthropic_vision_extract() -> int:
    if rc := _exists("9", _LLM_ANTHROPIC):
        return rc
    text = _read(_LLM_ANTHROPIC)
    # The implementation is `async def vision_extract` — pin both the
    # async-def shape AND that it appears AS a method of AnthropicProvider
    # (we lean on text-order: AnthropicProvider class is the only
    # consumer of vision_extract in this file).
    if not re.search(
        r"^\s+async\s+def\s+vision_extract\s*\(",
        text,
        re.MULTILINE,
    ):
        return _fail(
            "9",
            "providers/anthropic.py missing `async def vision_extract` "
            "method (Plan 24 T3 concrete implementation)",
        )
    # AnthropicProvider class must exist as the containing class.
    if not re.search(r"^class\s+AnthropicProvider\b", text, re.MULTILINE):
        return _fail(
            "9",
            "providers/anthropic.py missing `class AnthropicProvider`",
        )
    _gate(
        "9 — T3.b AnthropicProvider.vision_extract: `async def "
        "vision_extract` method lands inside the class"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T3.c: brain_core.ingest.ocr helper exists.
# ---------------------------------------------------------------------------


def _gate_10_t3_ocr_helper() -> int:
    if rc := _exists("10", _OCR):
        return rc
    text = _read(_OCR)
    # ocr_image is the public helper that T4 calls; OCR_OPERATION is the
    # canonical ledger-row tag so future cost-rollups reference one
    # string. Both must be exported from the module.
    if not re.search(
        r"^async\s+def\s+ocr_image\s*\(",
        text,
        re.MULTILINE,
    ):
        return _fail(
            "10",
            "ingest/ocr.py missing `async def ocr_image(...)` helper "
            "(Plan 24 T3 — wraps budget + LLM + ledger into one call)",
        )
    if not re.search(
        r'^OCR_OPERATION\s*=\s*[\'"]ocr[\'"]',
        text,
        re.MULTILINE,
    ):
        return _fail(
            "10",
            "ingest/ocr.py missing `OCR_OPERATION = \"ocr\"` constant "
            "(Plan 24 T3 D6 — canonical ledger-row tag)",
        )
    _gate(
        "10 — T3.c ingest.ocr: `ocr_image` async helper + "
        '`OCR_OPERATION = "ocr"` constant both exported'
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T4.a: pipeline ingest() runs the OCR pass.
# ---------------------------------------------------------------------------


def _gate_11_t4_pipeline_ocr_pass() -> int:
    if rc := _exists("11", _PIPELINE):
        return rc
    text = _read(_PIPELINE)
    # ocr_image must be imported (T4 wired the helper into the pipeline).
    if "from brain_core.ingest.ocr import ocr_image" not in text:
        return _fail(
            "11",
            "pipeline.py missing `from brain_core.ingest.ocr import "
            "ocr_image` (T4 helper consumption)",
        )
    # The pipeline must define a `_ocr_images` helper method AND the
    # main `ingest()` must call it. Pin both shapes — a regression that
    # defines the helper but forgets to wire it fails RED.
    if not re.search(
        r"^\s+async\s+def\s+_ocr_images\s*\(",
        text,
        re.MULTILINE,
    ):
        return _fail(
            "11",
            "pipeline.py missing `async def _ocr_images(...)` helper "
            "method (Plan 24 T4 Stage 5.5 OCR pass)",
        )
    if "self._ocr_images(" not in text:
        return _fail(
            "11",
            "pipeline.py `ingest()` does not call `self._ocr_images(...)` "
            "— OCR pass declared but not wired (T4 contract)",
        )
    _gate(
        "11 — T4.a pipeline OCR pass: `from ... import ocr_image` + "
        "`async def _ocr_images(...)` + `self._ocr_images(...)` call"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T4.b: OCR inline block format.
# ---------------------------------------------------------------------------


def _gate_12_t4_inline_block_format() -> int:
    text = _read(_PIPELINE)
    # `[Image: ...]` for docx (no slide context) and `[Image (slide N): ...]`
    # for pptx (slide-prefixed) are the two canonical formats per T4
    # outcome receipt. Both must appear in the pipeline source so a
    # regression that drops the slide-prefixed branch fails RED.
    if not re.search(r"\[Image\s*:", text):
        return _fail(
            "12",
            "pipeline.py missing `[Image: ...]` block format string "
            "(T4 docx inline marker)",
        )
    if not re.search(r"\[Image\s*\(slide", text):
        return _fail(
            "12",
            "pipeline.py missing `[Image (slide N): ...]` block format "
            "string (T4 pptx inline marker)",
        )
    _gate(
        "12 — T4.b inline block format: `[Image: ...]` + "
        "`[Image (slide N): ...]` patterns both present in pipeline.py"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T5: drop-zone accept list + source-row icon mapping.
# ---------------------------------------------------------------------------


def _gate_13_t5_frontend_accept_and_icons() -> int:
    if rc := _exists("13", _INBOX_STORE):
        return rc
    inbox_text = _read(_INBOX_STORE)
    # Both Office Open XML MIME types must appear in inbox-store's
    # INGEST_ACCEPT map. The MIME strings are the IANA-registered
    # identifiers per Plan 24 T5 receipt.
    docx_mime = (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )
    pptx_mime = (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    )
    if docx_mime not in inbox_text:
        return _fail(
            "13",
            f"inbox-store.ts missing docx MIME type `{docx_mime}`",
        )
    if pptx_mime not in inbox_text:
        return _fail(
            "13",
            f"inbox-store.ts missing pptx MIME type `{pptx_mime}`",
        )
    # IngestType union must include both new literals so the
    # source-row switch cases type-check.
    if '"docx"' not in inbox_text or '"pptx"' not in inbox_text:
        return _fail(
            "13",
            'inbox-store.ts IngestType union missing `"docx"` or `"pptx"` '
            "literal (T5 union extension)",
        )
    if rc := _exists("13", _SOURCE_ROW):
        return rc
    source_row_text = _read(_SOURCE_ROW)
    # The TypeIcon switch (NOT the typeLabel switch) must carry docx +
    # pptx cases. Both switches contain `case "docx":` / `case "pptx":`
    # in T5 — pin the TypeIcon-specific testid attributes (added in T5
    # specifically so the unit tests can pin "this branch ran").
    if 'data-testid="type-icon-docx"' not in source_row_text:
        return _fail(
            "13",
            "source-row.tsx TypeIcon missing `data-testid=\"type-icon-docx\"` "
            "case (T5 icon-mapping contract)",
        )
    if 'data-testid="type-icon-pptx"' not in source_row_text:
        return _fail(
            "13",
            "source-row.tsx TypeIcon missing `data-testid=\"type-icon-pptx\"` "
            "case (T5 icon-mapping contract)",
        )
    _gate(
        "13 — T5 frontend: docx + pptx MIME types in INGEST_ACCEPT, "
        "IngestType union extended, TypeIcon cases with testids landed"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T5.5: source_type read + inferIngestTypeFromFilename helper.
# ---------------------------------------------------------------------------


def _gate_14_t5_5_frontend_integration_fixes() -> int:
    inbox_text = _read(_INBOX_STORE)
    # T5.5 flipped the `loadRecent` read from `(it.type as IngestType)`
    # to `(it.source_type as IngestType)` so the backend's emitted
    # field name lands in the store. Pin the field-name pattern.
    if not re.search(
        r"it\.source_type\s+as\s+IngestType",
        inbox_text,
    ):
        return _fail(
            "14",
            "inbox-store.ts does NOT read `it.source_type as IngestType` "
            "in loadRecent (Plan 24 T5.5 backend field-name alignment)",
        )
    if rc := _exists("14", _DROP_ZONE):
        return rc
    drop_zone_text = _read(_DROP_ZONE)
    # The extension-sniff helper for optimistic rows. T5.5 added this
    # so drop-zone's optimistic rows render the correct icon during
    # upload (before recentIngests resolves with the backend's
    # source_type).
    if "inferIngestTypeFromFilename" not in drop_zone_text:
        return _fail(
            "14",
            "drop-zone.tsx missing `inferIngestTypeFromFilename` helper "
            "(Plan 24 T5.5 optimistic-row extension-sniff)",
        )
    # The helper must claim BOTH "docx" and "pptx" cases — pin the
    # case-arm patterns inside the file.
    if 'return "docx"' not in drop_zone_text:
        return _fail(
            "14",
            'drop-zone.tsx `inferIngestTypeFromFilename` missing `return "docx"` '
            "case (T5.5 extension-sniff contract)",
        )
    if 'return "pptx"' not in drop_zone_text:
        return _fail(
            "14",
            'drop-zone.tsx `inferIngestTypeFromFilename` missing `return "pptx"` '
            "case (T5.5 extension-sniff contract)",
        )
    _gate(
        "14 — T5.5 frontend integration: inbox-store reads "
        "`it.source_type as IngestType` + drop-zone defines "
        "`inferIngestTypeFromFilename` with docx + pptx cases"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T6 closure: todo.md row 24 ✅ + lessons.md Plan 24 section.
# ---------------------------------------------------------------------------


def _gate_15_t6_closure() -> int:
    if rc := _exists("15", _TODO):
        return rc
    todo_text = _read(_TODO)
    if re.search(r"\|\s*24\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail(
            "15",
            "tasks/todo.md row 24 not marked `✅ Complete`",
        )
    if rc := _exists("15", _LESSONS):
        return rc
    lessons_text = _read(_LESSONS)
    if "## Plan 24" not in lessons_text:
        return _fail(
            "15",
            "tasks/lessons.md missing `## Plan 24` closure section",
        )
    _gate(
        "15 — T6 closure: tasks/todo.md row 24 ✅; tasks/lessons.md "
        "has Plan 24 section"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t0_spec_handlers_table,
    _gate_2_t0_spec_ocr_rules,
    _gate_3_t0_spec_vision_cost_bullet,
    _gate_4_t0_source_type_enum,
    _gate_5_t1_docx_handler_and_registration,
    _gate_6_t1_5_content_sniff,
    _gate_7_t2_pptx_handler_and_dep,
    _gate_8_t3_llm_provider_vision_extract,
    _gate_9_t3_anthropic_vision_extract,
    _gate_10_t3_ocr_helper,
    _gate_11_t4_pipeline_ocr_pass,
    _gate_12_t4_inline_block_format,
    _gate_13_t5_frontend_accept_and_icons,
    _gate_14_t5_5_frontend_integration_fixes,
    _gate_15_t6_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 24 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
