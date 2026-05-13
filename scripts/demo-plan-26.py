#!/usr/bin/env python3
"""Plan 26 end-to-end demo — CRITICAL ClassifyOutput Literal fix + Plan 25
immediate aftermath (ScannedPDFError hard-remove + SSE walk-progress + per-
file filename apply UI).

Walks every substantive-task gate from
``tasks/plans/26-critical-fix-and-plan-25-aftermath.md`` (T1 → T4) plus
the closure marker. Mirrors the demo-plan-22 / demo-plan-23 / demo-
plan-24 / demo-plan-25 shape (cached file reads, single-purpose gate
functions, fail-fast main loop) but exercises a richer mix of live
behaviour:

- Gates 1-3 introspect the regenerated ``ClassifyOutput`` Literal via
  ``__args__`` and exercise Pydantic validation directly.
- Gate 4 asserts the import now raises ``ImportError``.
- Gate 5 grep-pins the source for ``ScannedPDFError`` (zero hits).
- Gate 6 spins up a >50-file tempfile fixture and consumes
  ``BulkImporter.plan_streaming()`` to confirm ≥1 ``walk_progress``
  event fires.
- Gate 7 stands up a FastAPI :class:`TestClient` against
  ``brain_api.create_app(mount_static_ui=False)`` and asserts the SSE
  endpoint's wire contract.
- Gate 8 round-trips all 4 ``WalkEvent`` Pydantic models through
  JSON.
- Gates 9-10 shell out to ``pnpm vitest run`` against the bulk-store
  + step-apply test files and gate on exit code.

Gate map
--------
 1   T1     ``ClassifyOutput.source_type.__args__`` contains all 8
            SourceType enum values.
 2   T1     Rendered classify-prompt text contains every backtick-
            wrapped SourceType value (verifies ``{source_types}``
            placeholder interpolation).
 3   T1     ``ClassifyOutput(source_type="docx", domain="research",
            confidence=0.9)`` validates without raising.
 4   T2     ``from brain_core.ingest.handlers.pdf import
            ScannedPDFError`` raises ``ImportError``.
 5   T2     Grep of ``packages/brain_core/src/brain_core/ingest/handlers/
            pdf.py`` returns ZERO matches for ``ScannedPDFError``.
 6   T3     ``BulkImporter.plan_streaming()`` yields ≥1
            ``walk_progress`` event for a fixture folder with >50
            files (live async generator consumption).
 7   T3     ``GET /api/bulk/walk-progress?path=<fixture>`` returns
            ``Content-Type: text/event-stream`` + the 4 expected event
            types in the correct order.
 8   T3     All 4 ``WalkEvent`` Pydantic models round-trip JSON
            serialize/deserialize via ``model_dump_json`` +
            ``model_validate_json``.
 9   T4     ``pnpm vitest run apps/brain_web/src/lib/state/bulk-
            store.test.ts`` exits zero (bulk-store ``setCurrentFile`` +
            lifecycle clearing).
10   T4     ``pnpm vitest run apps/brain_web/src/components/bulk/step-
            apply.test.tsx`` exits zero (apply-current-file element
            renders truncated path when set).

Closure (T5) is this script; final stdout line on a clean run is
``PLAN 26 DEMO OK``.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_CORE = _REPO_ROOT / "packages" / "brain_core"
_BRAIN_API = _REPO_ROOT / "packages" / "brain_api"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"

_PDF_HANDLER = (
    _BRAIN_CORE / "src" / "brain_core" / "ingest" / "handlers" / "pdf.py"
)
_BULK_STORE_TEST = (
    _BRAIN_WEB / "src" / "lib" / "state" / "bulk-store.test.ts"
)
_STEP_APPLY_TEST = (
    _BRAIN_WEB / "src" / "components" / "bulk" / "step-apply.test.tsx"
)


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
# Gate 1 — T1: ClassifyOutput.source_type.__args__ contains all 8 SourceType
# values.
# ---------------------------------------------------------------------------


def _gate_1_t1_classify_literal_full_coverage() -> int:
    try:
        schemas_mod = importlib.import_module("brain_core.prompts.schemas")
        types_mod = importlib.import_module("brain_core.ingest.types")
    except ImportError as exc:
        return _fail("1", f"could not import schemas/types: {exc}")
    ClassifyOutput = schemas_mod.ClassifyOutput
    SourceType = types_mod.SourceType
    source_type_field = ClassifyOutput.model_fields["source_type"]
    annotation = source_type_field.annotation
    # Pydantic stores the Literal's args at __args__ regardless of how it
    # was constructed (PEP 646 unpack OR explicit list).
    if not hasattr(annotation, "__args__"):
        return _fail(
            "1",
            f"ClassifyOutput.source_type annotation has no __args__; got "
            f"{annotation!r}",
        )
    literal_args = set(annotation.__args__)
    expected = {s.value for s in SourceType}
    if literal_args != expected:
        missing = expected - literal_args
        extra = literal_args - expected
        return _fail(
            "1",
            f"ClassifyOutput.source_type Literal drift: missing={sorted(missing)}, "
            f"extra={sorted(extra)}; expected exactly {sorted(expected)}",
        )
    # Spot-check the two Plan 24 additions (the precise gap that motivated
    # Plan 26 T1).
    if "docx" not in literal_args:
        return _fail(
            "1",
            "`docx` missing from ClassifyOutput.source_type Literal — Plan 24 "
            "drift",
        )
    if "pptx" not in literal_args:
        return _fail(
            "1",
            "`pptx` missing from ClassifyOutput.source_type Literal — Plan 24 "
            "drift",
        )
    _gate(
        f"1 — T1 ClassifyOutput.source_type.__args__ = "
        f"{sorted(literal_args)} (all 8 SourceType values present; "
        f"`docx` + `pptx` covered)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1: rendered classify-prompt contains all 8 backticked source-type
# values.
# ---------------------------------------------------------------------------


def _gate_2_t1_classify_prompt_renders_all_types() -> int:
    try:
        types_mod = importlib.import_module("brain_core.ingest.types")
        loader_mod = importlib.import_module("brain_core.prompts.loader")
    except ImportError as exc:
        return _fail("2", f"could not import loader/types: {exc}")
    SourceType = types_mod.SourceType
    # Resolve the classify prompt via the package loader. The constant
    # name + interpolation pattern matches the production code at
    # ``classifier.py:21`` / ``pipeline.py:83``.
    classify_prompt = loader_mod.load_prompt("classify")
    source_types_rendered = ", ".join(f"`{s.value}`" for s in SourceType)
    rendered = classify_prompt.render_system(
        domains="research, personal",
        source_types=source_types_rendered,
    )
    for s in SourceType:
        needle = f"`{s.value}`"
        if needle not in rendered:
            return _fail(
                "2",
                f"rendered classify-prompt missing backticked source-type "
                f"`{s.value}` — {{source_types}} interpolation broken",
            )
    _gate(
        "2 — T1 classify prompt: rendered output contains every backticked "
        "SourceType value (`text` / `url` / `pdf` / `email` / `transcript` / "
        "`docx` / `pptx` / `tweet`) via {source_types} placeholder"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T1: ClassifyOutput(source_type="docx", ...) validates.
# ---------------------------------------------------------------------------


def _gate_3_t1_classify_docx_validates() -> int:
    try:
        schemas_mod = importlib.import_module("brain_core.prompts.schemas")
    except ImportError as exc:
        return _fail("3", f"could not import schemas: {exc}")
    ClassifyOutput = schemas_mod.ClassifyOutput
    # The exact construction from the plan-doc demo gate description.
    try:
        out = ClassifyOutput(source_type="docx", domain="research", confidence=0.9)
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "3",
            f"ClassifyOutput(source_type='docx', ...) raised: "
            f"{type(exc).__name__}: {exc}",
        )
    if out.source_type != "docx":
        return _fail(
            "3",
            f"ClassifyOutput parsed `docx` but stored {out.source_type!r}",
        )
    # Belt-and-suspenders: pptx also validates (the second Plan 24 addition).
    try:
        out_pptx = ClassifyOutput(
            source_type="pptx", domain="research", confidence=0.5
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "3",
            f"ClassifyOutput(source_type='pptx', ...) raised: "
            f"{type(exc).__name__}: {exc}",
        )
    if out_pptx.source_type != "pptx":
        return _fail(
            "3",
            f"ClassifyOutput parsed `pptx` but stored {out_pptx.source_type!r}",
        )
    _gate(
        "3 — T1 ClassifyOutput(source_type='docx', ...) + ('pptx', ...) "
        "both validate without raising"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T2: ScannedPDFError import raises ImportError.
# ---------------------------------------------------------------------------


def _gate_4_t2_scanned_pdf_error_import_fails() -> int:
    # Use importlib so a stale module cache from earlier imports doesn't
    # mask a real surface — and capture the actual exception class.
    try:
        pdf_mod = importlib.import_module("brain_core.ingest.handlers.pdf")
    except ImportError as exc:
        return _fail("4", f"could not import brain_core.ingest.handlers.pdf: {exc}")
    if hasattr(pdf_mod, "ScannedPDFError"):
        return _fail(
            "4",
            "`ScannedPDFError` is still defined on "
            "brain_core.ingest.handlers.pdf — Plan 26 T2 hard-remove "
            "(D2) did not land",
        )
    # The `from ... import ScannedPDFError` form must raise ImportError
    # (NOT ModuleNotFoundError — the module exists; the name doesn't).
    try:
        exec(  # noqa: S102
            "from brain_core.ingest.handlers.pdf import ScannedPDFError",
            {},
        )
    except ImportError:
        _gate(
            "4 — T2 `from brain_core.ingest.handlers.pdf import "
            "ScannedPDFError` raises ImportError (hard-remove per D2)"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "4",
            f"import raised unexpected exception type: {type(exc).__name__}: {exc}",
        )
    return _fail(
        "4",
        "`from brain_core.ingest.handlers.pdf import ScannedPDFError` did "
        "NOT raise — the name is still importable",
    )


# ---------------------------------------------------------------------------
# Gate 5 — T2: grep of pdf.py returns zero matches for ScannedPDFError.
# ---------------------------------------------------------------------------


def _gate_5_t2_pdf_py_no_scanned_pdf_error_references() -> int:
    if rc := _exists("5", _PDF_HANDLER):
        return rc
    pdf_text = _read(_PDF_HANDLER)
    matches = [
        (idx, line)
        for idx, line in enumerate(pdf_text.splitlines(), start=1)
        if "ScannedPDFError" in line
    ]
    if matches:
        sample = "\n    ".join(f"{idx}: {line.strip()}" for idx, line in matches[:5])
        return _fail(
            "5",
            f"handlers/pdf.py still references `ScannedPDFError` at "
            f"{len(matches)} site(s):\n    {sample}",
        )
    _gate(
        "5 — T2 handlers/pdf.py: zero references to `ScannedPDFError` "
        "(class + docstring + comment all removed)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T3: BulkImporter.plan_streaming() yields ≥1 walk_progress event.
# ---------------------------------------------------------------------------


def _gate_6_t3_plan_streaming_emits_walk_progress() -> int:
    try:
        bulk_mod = importlib.import_module("brain_core.ingest.bulk")
        walk_events_mod = importlib.import_module("brain_core.ingest.walk_events")
        pipeline_mod = importlib.import_module("brain_core.ingest.pipeline")
        fake_mod = importlib.import_module("brain_core.llm.fake")
        vault_writer_mod = importlib.import_module("brain_core.vault.writer")
    except ImportError as exc:
        return _fail("6", f"could not import deps for plan_streaming gate: {exc}")
    if not hasattr(bulk_mod, "BulkImporter"):
        return _fail("6", "brain_core.ingest.bulk missing BulkImporter")
    if not hasattr(bulk_mod.BulkImporter, "plan_streaming"):
        return _fail(
            "6",
            "BulkImporter.plan_streaming() missing — Plan 26 T3 backend "
            "not landed",
        )
    WalkProgress = walk_events_mod.WalkProgress
    WalkStarted = walk_events_mod.WalkStarted
    WalkComplete = walk_events_mod.WalkComplete

    async def _drive() -> list[object]:
        with tempfile.TemporaryDirectory() as tmp:
            # Real IngestPipeline construction (matches the canonical
            # pattern from packages/brain_core/tests/ingest/
            # test_bulk_streaming.py:32). plan_streaming reads
            # ``self._pipeline.handlers`` for the handler-claim filter
            # but does not classify / summarize / integrate — so the
            # FakeLLMProvider with no queued responses is fine.
            vault_root = Path(tmp) / "vault"
            vault_root.mkdir(parents=True)
            (vault_root / ".brain").mkdir(parents=True)
            for sub in ("sources", "entities", "concepts", "synthesis"):
                (vault_root / "research" / sub).mkdir(parents=True)
            pipeline = pipeline_mod.IngestPipeline(
                vault_root=vault_root,
                writer=vault_writer_mod.VaultWriter(vault_root=vault_root),
                llm=fake_mod.FakeLLMProvider(),
                summarize_model="claude-sonnet-4-6",
                integrate_model="claude-sonnet-4-6",
                classify_model="claude-haiku-4-5-20251001",
            )
            importer = bulk_mod.BulkImporter(pipeline)

            source = Path(tmp) / "source"
            source.mkdir()
            # Walker emits a WalkProgress every 50 candidate files. Seed
            # 60 .txt files so at least one progress event MUST fire
            # (60 // 50 = 1). The handler-claim filter passes .txt
            # straight through so total_count == 60 as well.
            for i in range(60):
                (source / f"note-{i:02d}.txt").write_text(
                    "hello world\n", encoding="utf-8"
                )

            events: list[object] = []
            async for ev in importer.plan_streaming(source):
                events.append(ev)
            return events

    try:
        events = asyncio.run(_drive())
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "6",
            f"plan_streaming(...) raised: {type(exc).__name__}: {exc}",
        )

    if not events:
        return _fail("6", "plan_streaming yielded zero events")
    if not isinstance(events[0], WalkStarted):
        return _fail(
            "6",
            f"first event is {type(events[0]).__name__}; expected WalkStarted",
        )
    if not isinstance(events[-1], WalkComplete):
        return _fail(
            "6",
            f"last event is {type(events[-1]).__name__}; expected WalkComplete",
        )
    progress_events = [e for e in events if isinstance(e, WalkProgress)]
    if not progress_events:
        return _fail(
            "6",
            f"no WalkProgress events in stream (len={len(events)}); "
            f"with 60 .txt files + 50-file interval, ≥1 progress event "
            f"must fire",
        )
    final = events[-1]
    # 60 .txt files all pass the handler-claim filter → total_count == 60.
    assert isinstance(final, WalkComplete)
    if final.total_count != 60:
        return _fail(
            "6",
            f"WalkComplete.total_count = {final.total_count}; expected 60",
        )
    _gate(
        f"6 — T3 BulkImporter.plan_streaming() emitted "
        f"{len(events)} events ({len(progress_events)} WalkProgress) + "
        f"WalkComplete(total_count=60) for a 60-file fixture"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T3: GET /api/bulk/walk-progress emits text/event-stream + the 4
# expected event types in order.
# ---------------------------------------------------------------------------


def _gate_7_t3_sse_endpoint_wire_contract() -> int:
    try:
        from brain_api import create_app
        from fastapi.testclient import TestClient
    except ImportError as exc:
        return _fail("7", f"could not import brain_api / TestClient: {exc}")

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        vault.mkdir(parents=True, exist_ok=True)
        (vault / ".brain").mkdir(parents=True, exist_ok=True)
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (vault / "research" / sub).mkdir(parents=True, exist_ok=True)
        (vault / "research" / "index.md").write_text(
            "# research\n", encoding="utf-8", newline="\n"
        )
        (vault / "research" / "log.md").write_text(
            "# log\n", encoding="utf-8", newline="\n"
        )
        (vault / "BRAIN.md").write_text(
            "# BRAIN\n", encoding="utf-8", newline="\n"
        )
        source = Path(tmp) / "source"
        source.mkdir()
        # Seed >50 files so a walk_progress event MUST appear in the
        # stream, matching the plan-doc gate description "4 expected
        # event types in stream order".
        for i in range(55):
            (source / f"n-{i:02d}.txt").write_text("x", encoding="utf-8")

        app = create_app(
            vault_root=vault,
            allowed_domains=("research",),
            mount_static_ui=False,
        )

        with TestClient(app, base_url="http://localhost") as client:
            token = app.state.ctx.token
            if token is None:
                return _fail("7", "app.state.ctx.token is None")
            r = client.get(
                "/api/bulk/walk-progress",
                params={"path": str(source), "token": token},
                headers={"Origin": "http://localhost:4317"},
            )

        if r.status_code != 200:
            return _fail(
                "7",
                f"GET /api/bulk/walk-progress returned {r.status_code}; "
                f"body: {r.text[:200]}",
            )
        ctype = r.headers.get("content-type", "")
        if not ctype.startswith("text/event-stream"):
            return _fail(
                "7",
                f"Content-Type was {ctype!r}; expected text/event-stream",
            )

        # Parse SSE frames — each event is a `data: <json>\n\n` block.
        event_types: list[str] = []
        for chunk in r.text.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            for line in chunk.splitlines():
                if line.startswith("data: "):
                    payload = json.loads(line[len("data: "):])
                    event_types.append(str(payload.get("type")))

        if not event_types:
            return _fail("7", "no SSE frames decoded from response body")
        if event_types[0] != "walk_started":
            return _fail(
                "7",
                f"first event type {event_types[0]!r}; expected `walk_started`",
            )
        if event_types[-1] != "walk_complete":
            return _fail(
                "7",
                f"last event type {event_types[-1]!r}; expected `walk_complete`",
            )
        if "walk_progress" not in event_types:
            return _fail(
                "7",
                f"no `walk_progress` event in stream (55-file fixture "
                f"with 50-file interval guarantees ≥1); types: {event_types}",
            )

    _gate(
        f"7 — T3 SSE endpoint: Content-Type=text/event-stream + ordered "
        f"events {event_types[0]} → walk_progress → {event_types[-1]} "
        f"({len(event_types)} frames total)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T3: all 4 WalkEvent Pydantic models round-trip JSON.
# ---------------------------------------------------------------------------


def _gate_8_t3_walk_event_models_roundtrip() -> int:
    try:
        walk_events_mod = importlib.import_module("brain_core.ingest.walk_events")
    except ImportError as exc:
        return _fail("8", f"could not import walk_events: {exc}")
    WalkStarted = walk_events_mod.WalkStarted
    WalkProgress = walk_events_mod.WalkProgress
    WalkComplete = walk_events_mod.WalkComplete
    WalkError = walk_events_mod.WalkError

    cases: list[tuple[type, dict[str, object]]] = [
        (WalkStarted, {"path": "/tmp/source"}),
        (WalkProgress, {"files_seen": 50, "current_path": "/tmp/source/x.txt"}),
        (WalkComplete, {"total_count": 137, "plan_id": "abc-123"}),
        (
            WalkError,
            {
                "error_message": "boom",
                "error_code": "permission_denied",
            },
        ),
    ]
    for cls, kwargs in cases:
        instance = cls(**kwargs)
        # model_dump_json round-trip — the wire shape the SSE endpoint
        # actually emits.
        wire = instance.model_dump_json()
        try:
            decoded_dict = json.loads(wire)
        except json.JSONDecodeError as exc:
            return _fail(
                "8",
                f"{cls.__name__}.model_dump_json produced invalid JSON: {exc}",
            )
        # `type` discriminator must be embedded.
        if "type" not in decoded_dict:
            return _fail(
                "8",
                f"{cls.__name__} wire payload missing `type` discriminator: "
                f"{decoded_dict}",
            )
        # Round-trip via model_validate_json — concrete class equality.
        roundtripped = cls.model_validate_json(wire)
        if roundtripped != instance:
            return _fail(
                "8",
                f"{cls.__name__} round-trip mismatch: original={instance!r} "
                f"!= roundtripped={roundtripped!r}",
            )
    _gate(
        "8 — T3 all 4 WalkEvent models (WalkStarted / WalkProgress / "
        "WalkComplete / WalkError) round-trip via model_dump_json + "
        "model_validate_json with `type` discriminator preserved"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T4: pnpm vitest run bulk-store.test.ts exits zero.
# ---------------------------------------------------------------------------


def _run_vitest(label: str, test_path: Path) -> int:
    if rc := _exists(label, test_path):
        return rc
    # pnpm vitest run is the canonical per-task verification recipe for
    # apps/brain_web/ per ``feedback_tsc_vs_vitest.md``. We invoke from
    # the brain_web cwd so workspace-local config resolves; the path arg
    # is relative-to-cwd.
    rel = test_path.relative_to(_BRAIN_WEB)
    try:
        proc = subprocess.run(
            ["pnpm", "vitest", "run", str(rel)],
            cwd=str(_BRAIN_WEB),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except FileNotFoundError as exc:
        return _fail(
            label,
            f"`pnpm` not found on PATH — install pnpm or run with the "
            f"correct shell: {exc}",
        )
    except subprocess.TimeoutExpired:
        return _fail(label, "vitest exceeded 180s timeout")
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-1500:] + (proc.stderr or "")[-1500:]
        return _fail(
            label,
            f"vitest exited {proc.returncode} for {rel}; tail:\n{tail}",
        )
    # Spot-check the stdout for a "passed" string to defend against
    # silent zero-test runs.
    if "passed" not in (proc.stdout or "").lower():
        return _fail(
            label,
            f"vitest output for {rel} did not mention `passed` — possible "
            f"zero-test run; stdout tail: {(proc.stdout or '')[-500:]}",
        )
    return 0


def _gate_9_t4_bulk_store_vitest_green() -> int:
    rc = _run_vitest("9", _BULK_STORE_TEST)
    if rc != 0:
        return rc
    _gate(
        "9 — T4 pnpm vitest run src/lib/state/bulk-store.test.ts: exit "
        "zero (setCurrentFile + lifecycle clearing pins green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T4: pnpm vitest run step-apply.test.tsx exits zero.
# ---------------------------------------------------------------------------


def _gate_10_t4_step_apply_vitest_green() -> int:
    rc = _run_vitest("10", _STEP_APPLY_TEST)
    if rc != 0:
        return rc
    _gate(
        "10 — T4 pnpm vitest run src/components/bulk/step-apply.test.tsx: "
        "exit zero (apply-current-file element renders truncated path)"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t1_classify_literal_full_coverage,
    _gate_2_t1_classify_prompt_renders_all_types,
    _gate_3_t1_classify_docx_validates,
    _gate_4_t2_scanned_pdf_error_import_fails,
    _gate_5_t2_pdf_py_no_scanned_pdf_error_references,
    _gate_6_t3_plan_streaming_emits_walk_progress,
    _gate_7_t3_sse_endpoint_wire_contract,
    _gate_8_t3_walk_event_models_roundtrip,
    _gate_9_t4_bulk_store_vitest_green,
    _gate_10_t4_step_apply_vitest_green,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 26 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
