# Prompt contract tests (VCR cassettes)

This project uses [`vcrpy`](https://vcrpy.readthedocs.io/) via
[`pytest-vcr`](https://github.com/ktosiek/pytest-vcr) to record and replay
real Anthropic API responses for prompt contract tests. The goal is to catch
schema drift — if Anthropic changes how a model formats JSON output, the
cassette-backed test will fail where a `FakeLLMProvider` test cannot.

## How it works

1. **Record mode.** On the first run with `RUN_LIVE_LLM_TESTS=1`, `vcrpy`
   intercepts every HTTP call, lets the real request hit Anthropic, and saves
   the request + response to a YAML file under
   `packages/brain_core/tests/prompts/cassettes/`.
2. **Replay mode** (every subsequent run). `vcrpy` intercepts the same HTTP
   call, looks up the matching request in the cassette, and returns the
   recorded response without touching the network. Tests are deterministic
   and free.
3. **Cassettes are committed to git** alongside the tests.

## Running the tests

### Normal (replay) mode — no API key required

```
uv run pytest packages/brain_core/tests/prompts -q
```

If a cassette is missing for a VCR-marked test, the test is **skipped** with
a clear message. No network calls.

### Record mode — API key required

```
export ANTHROPIC_API_KEY=sk-...
RUN_LIVE_LLM_TESTS=1 uv run pytest packages/brain_core/tests/prompts -v -m vcr
```

This will make real HTTP calls, save cassettes, and cost a small amount of
token budget. After recording, commit the cassettes:

```
git add packages/brain_core/tests/prompts/cassettes/
git commit -m "test(brain_core): record prompt cassettes"
```

## Writing a VCR-marked test

Template:

```python
import os
from pathlib import Path
import pytest

_CASSETTES = Path(__file__).parent / "cassettes"


@pytest.mark.vcr
@pytest.mark.skipif(
    not (_CASSETTES / "test_summarize.yaml").exists()
    and os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason="cassette not recorded; set RUN_LIVE_LLM_TESTS=1 to record",
)
async def test_summarize_contract():
    # make the real API call here — vcrpy intercepts it
    ...
```

## Redaction

The `vcr_config` fixture in `tests/prompts/conftest.py` automatically
redacts these headers before writing cassettes:

- `authorization`
- `x-api-key`
- `anthropic-api-key`

Before committing new cassettes, grep them for any `sk-` or token-like
strings that may have slipped through.

## Chat prompts (Plan 03 Task 21)

Four chat-related prompts have rendering tests and deferred cassette
skeletons:

- `test_chat_ask.py` — Ask mode (plain-text prompt loaded via
  `brain_core.chat.modes.MODES`)
- `test_chat_brainstorm.py` — Brainstorm mode (plain-text)
- `test_chat_draft.py` — Draft mode (plain-text)
- `test_chat_autotitle.py` — structured-output prompt with YAML
  frontmatter, loaded via `load_prompt("chat_autotitle")`

The rendering tests run on every CI — they assert structural properties
of the prompt text (length, required keywords, template placeholders)
without ever hitting the network. The contract test skeletons are
decorated with `@pytest.mark.skipif(True, ...)` and raise
`NotImplementedError` in the body, so they always skip until a future
session records real cassettes.

### Recording the chat cassettes

When an Anthropic API key is available:

```
export ANTHROPIC_API_KEY=sk-...
RUN_LIVE_LLM_TESTS=1 uv run pytest packages/brain_core/tests/prompts -v -k chat
```

Then:
1. Remove the `skipif(True, ...)` from each contract test.
2. Fill in the body with a real `LLMRequest` + `AnthropicProvider` call
   plus assertions on the response shape.
3. Commit the new cassettes under `cassettes/`.

## Current status

**Task 20 (scaffolding):** complete. Marker registered, VCR config in place,
cassettes dir present but empty.

**Task 21 (chat rendering tests + cassette skeletons):** complete. 12
rendering tests green, 4 contract test skeletons skipped.

**Recording + contract assertions:** deferred. Will land whenever an
Anthropic API key is available.

## Plan 04 — MCP tool cassettes

Three MCP-layer ingest tools have deferred contract test skeletons under
`packages/brain_mcp/tests/prompts/`:

- `test_brain_ingest_contract.py` — `brain_ingest` tool
- `test_brain_classify_contract.py` — `brain_classify` tool
- `test_brain_bulk_import_contract.py` — `brain_bulk_import` tool

Each is a real-API contract test (the MCP tool layer calls the actual
Anthropic API) and is **not a merge gate**. They run in a dedicated CI job
gated on `ANTHROPIC_API_KEY` and never block PRs. Per Plan 04 D9a, no
cassettes are recorded yet; each skeleton is decorated with
`@pytest.mark.skipif(True, ...)` and raises `NotImplementedError` so
accidental skipif removal fails loud.

### Recording the MCP cassettes

```
export ANTHROPIC_API_KEY=sk-...
RUN_LIVE_LLM_TESTS=1 uv run pytest -k brain_ingest_contract packages/brain_mcp/tests/prompts -v
```

Then for each contract test:
1. Remove the `@pytest.mark.skipif(True, ...)` decorator.
2. Replace the `NotImplementedError` body with a real assertion against
   the recorded response (PatchSet shape, domain classification, cost
   ledger entry, etc.).
3. Commit the new cassette under
   `packages/brain_mcp/tests/prompts/cassettes/`.
