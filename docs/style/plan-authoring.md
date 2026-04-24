# Plan-authoring style guide

> Closes item #37 in `docs/v0.1.0-known-issues.md`.
> Consolidates the plan-authoring retrospective lessons from `tasks/lessons.md`
> that accumulated through Plans 01–08 but never made it into a reusable
> reference. Apply when writing any plan under `tasks/plans/`.

Plans live in `tasks/plans/NN-<name>.md` and get executed task-by-task by a
fresh subagent per task (see `superpowers:subagent-driven-development`). Each
task's spec becomes the subagent's whole world for that turn, so a bug in the
spec costs one review round minimum. The rules below eliminate the most
common, most expensive classes of spec bug we hit across Plans 01–08.

## 1. Verify real APIs before writing task prompts

Plans 03 and 05 both shipped spec text that referenced **imagined APIs** —
classes and methods that didn't exist in the real source tree.

- Plan 03 referenced `PromptLoader` class and `FakeLLMProvider.queue_response`
  when the real shapes were the `load_prompt` function and `FakeLLMProvider.queue`.
- Plan 05 referenced a non-existent `ChatSession.persist()` method and a
  `load_or_create` constructor that was never built (what actually shipped
  was an additive `initial_turns=` kwarg).

**Rule.** Before writing a task that invokes an existing class, open the
source file in the editor and paste the real signature into the plan text.
Imagined APIs waste one review round per task.

- `tasks/lessons.md:156` (Plan 03)
- `tasks/lessons.md:221` (Plan 05)

## 2. Size fixtures to clear configurable thresholds

Plan 02 Task 5's spec suggested a PDF fixture (`"Plan 02 PDF fixture\n…"` —
about 49 chars) that was below `PDFHandler.min_chars=200`. The happy-path
test in the spec would have spuriously raised `ScannedPDFError` — the
implementer caught it and expanded the fixture to ~295 chars while
preserving the required assertion substrings.

**Rule.** When a handler or function has a configurable threshold AND the
spec's happy-path test uses a fixture that could be measured against the
threshold, explicitly size the fixture to clear it. Add a one-line comment
in the spec noting why the size matters.

- `tasks/lessons.md:37` (Plan 02 Task 5 — PDF `min_chars`)

## 3. Walk string assertions against fixture values by hand

Plan 02 Task 10's spec produced `"Tweet by Andrej Karpathy"` (capital K in
"Karpathy") while the test assertion was `"karpathy" in es.title` (lowercase
k). Case-sensitive substring checks are a frequent spec-bug source because
they look correct at a glance.

**Rule.** For every `assert "X" in value` check in a spec, mentally run the
spec's own fixture through whatever constructs `value`, then eyeball the
comparison character-by-character. If the spec includes case variants
(title-case names, lowercase slugs), call them out explicitly.

- `tasks/lessons.md:39` (Plan 02 Task 10 — "karpathy" case sensitivity)

## 4. Use `==` (not `is`) for objects that round-trip through serialization

Plan 03 Task 10 asserted `result.proposed_patch is env_obj` where `env_obj`
was a `PendingEnvelope` that `store.list()` re-reads from disk and
reconstructs. Identity equality is structurally impossible across a
serialization round-trip; the implementer relaxed it to `==`.

**Rule.** If an assertion involves an object that round-trips through any
serializer (pydantic JSON, pickle, SQLite row, filesystem read-back), use
`==` not `is`. Reserve `is` for singletons (`None`, `Ellipsis`, `NotImplemented`)
and interned constants you're sure of.

- `tasks/lessons.md:156` (Plan 03 Task 10 — `PendingEnvelope` round-trip)

## 5. State-detection checks should count invariants, not totals

Plan 03 Task 18 used `len(_turns) == 4` to detect "end of turn 2" in the
chat loop. But any `SYSTEM` turn appended by `switch_mode`, `switch_scope`,
or `set_open_doc` between turns 1 and 2 bumps the count to 5 at the moment
the check fires — so the check never matches again and the feature
silently breaks. Fixed by counting `USER` turns instead (monotonic +1 per
real turn).

**Rule.** State-detection logic in a spec should count *invariant* data
(user turns, committed patches, applied migrations), not *all* data (total
turns, total rows). If the spec includes a total count as a check, ask
yourself "what could legitimately inflate this that I don't care about?" —
if the answer isn't "nothing", use a filtered count.

- `tasks/lessons.md:158` (Plan 03 Task 18 — `len(turns) == 4` fragility)

## 6. Document scope deviations explicitly

Plan 03 Tasks 14a and 15 both touched Plan 01/02 code (`VaultWriter.rename_file`
and the `LLMProvider` tool_use extension). Both were additive, preserved
existing behavior, and passed regression with zero Plan 02 test changes —
but the plan was explicit in advance that these were approved deviations.

**Rule.** Touching existing code from earlier plans is OK when **all three**
are true:
1. The change is strictly additive (no signature changes, no behavior
   removal).
2. There is a clear hard regression gate (existing test suite stays green
   unmodified).
3. The plan documents the exception explicitly at the top of the task.

If any of the three fails, the work belongs in a new plan, not an extension
of an in-flight one.

- `tasks/lessons.md:158` (Plan 03 additive deviations)

## 7. Writers go through the LF enforcer

Plan 03 shipped `_write_rename_undo_record` without `newline="\n"`, which
would have produced CRLF on Windows. A single file writer missing the LF
kwarg breaks cross-platform vault content.

**Rule.** When a spec asks a task to write content to disk, specify one of:
- `brain_core.vault.writer.VaultWriter._atomic_write` (already enforces LF)
- `os.replace` + explicit `encoding="utf-8", newline="\n"`
- A regression test that monkeypatches `Path.write_text` to assert the
  `newline="\n"` kwarg was passed.

Never write content to disk without one of these three in the task text.

- `tasks/lessons.md:158` (Plan 03 Task 22 — rename undo record missing `newline="\n"`)

## 8. Per-task review gate

Every task in a plan should close with a review subsection that answers:

- **Real APIs verified?** Imagined APIs (rule 1) are easiest to catch at
  plan-authoring time — easier than at subagent-implementing time.
- **String assertions walked?** Every `"X" in value` has been traced
  through the fixture values by hand (rule 3).
- **Thresholds checked?** Every configurable threshold referenced in the
  task has been cross-checked against the spec's own test fixtures (rule 2).
- **Serialization round-trips flagged?** `is`-vs-`==` audit for any
  assertion that reads something back from disk / JSON / SQLite (rule 4).
- **Count checks are invariant?** `len(...) == N` patterns reviewed
  against the "what could legitimately inflate this" question (rule 5).
- **Scope deviations documented?** Anything touching earlier-plan code
  has the three justifications spelled out (rule 6).
- **Writer goes through LF enforcer?** Any disk write has the LF discipline
  in place (rule 7).

Treat this as a 2-minute self-review per task. Catching one spec bug here
saves ~15 minutes of subagent round-trip + reviewer time downstream.

## Appendix — lesson sources

Every rule above cites the `tasks/lessons.md` line(s) where it was first
raised. When updating this guide, cite the new lesson line(s) explicitly so
the provenance stays auditable.

```text
Rule 1 (real APIs)        tasks/lessons.md:156, :221
Rule 2 (fixture size)     tasks/lessons.md:37
Rule 3 (string asserts)   tasks/lessons.md:39
Rule 4 (== vs is)         tasks/lessons.md:156
Rule 5 (invariant count)  tasks/lessons.md:158
Rule 6 (scope deviation)  tasks/lessons.md:158
Rule 7 (LF writers)       tasks/lessons.md:158
```
