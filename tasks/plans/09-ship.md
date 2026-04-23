# Plan 09 — Ship v0.1.0

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ship `v0.1.0` — the first real GitHub release. After this plan, a user on a clean Mac or Windows 11 box can run the install command from the README, complete the setup wizard, and start using brain end-to-end. The project goes from "complete codebase" to "shippable product."

**Architecture:** no new architecture. Plan 09 is a ship plan — versioning, packaging, docs, QA, and the first tag + release.

**What Plan 09 adds:**
- Version `0.1.0` pinned across brain_core, brain_cli, brain_mcp, brain_api, and a top-level `VERSION` file.
- A `scripts/release.sh` that produces a universal tarball (Python source + prebuilt `apps/brain_web/out/`) + SHA256 sidecar.
- `v0.1.0` GitHub release with that tarball attached.
- `install.sh` + `install.ps1` default `BRAIN_RELEASE_URL` flipped from placeholder to the real GitHub release asset URL.
- `brain start` update-check nudge (non-blocking, opt-out via `BRAIN_NO_UPDATE_CHECK=1`).
- README, LICENSE, CONTRIBUTING, privacy doc + 6–8 screenshots captured during the QA sweep.
- Clean-Mac + clean-Windows VM dry runs of the real release via the Plan 08 harness.
- Full 104-item manual-QA sweep receipt.
- `plan-09-ship` + `v0.1.0` tags pushed to origin.

**Decisions pinned (Q1–Q4):**
- **Q1a** — Universal single tarball. Python source + prebuilt UI. fnm/pnpm needed at install (for future upgrades) + upgrade time; never on global PATH.
- **Q2a** — `brain start` runs a background update-check (3s timeout) and prints a one-line nudge after the "running at ..." line if a newer version exists. Opt-out `BRAIN_NO_UPDATE_CHECK=1`.
- **Q3a** — Full 104-item manual-QA sweep on primary machine against the installed v0.1.0. Receipt at `docs/testing/v0.1.0-qa-receipt.md`.
- **Q4b** — Screenshots only (no video). 6–8 stills captured during the Q3a sweep.

**Demo gate:** `uv run python scripts/demo-plan-09.py`:
1. Cuts a v0.1.0 tarball via `scripts/release.sh` into a temp dir.
2. Runs install.sh against that tarball into a tmp install dir; `brain doctor` green.
3. `brain start` with update-check mocked to report a newer version; verify the nudge is printed.
4. Verify `v0.1.0` appears in `brain --version` output and in `/api/setup-status`.
5. Smoke-test one chat turn + ingest + pending approve (same as Plan 08 demo).
6. `brain uninstall --yes` + verify clean teardown.
7. Prints `PLAN 09 DEMO OK` on exit 0.

**Owning subagents:**
- `brain-installer-engineer` — Tasks 1, 4, 7, 8 (version bump, update-check, release script, GitHub release + URL flip).
- `brain-test-engineer` — Tasks 2, 9, 10, 11, 13 (known-issues triage, VM dry runs, manual QA, demo + close + tag).
- `brain-core-engineer` — Task 3 (CHANGELOG authoring) if needed; can also be test-engineer.
- `brain-prompt-engineer` or main-loop — Tasks 5, 6, 12 (README + docs + screenshot curation).

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-08-install` tag at `origin/main` (✓ done).
- Confirm a GitHub release can be created on the repo (main loop has push + release permissions).

---

## Scope — in and out

**In scope for Plan 09:**
- Version pinning to `0.1.0` across all packages + workspace.
- Universal-tarball release packaging (Q1a) via `scripts/release.sh`.
- First GitHub release at `v0.1.0` with tarball + SHA256 assets.
- `install.sh` / `install.ps1` real-URL wiring (default `BRAIN_RELEASE_URL` no longer needs env override).
- `brain start` update-check nudge (Q2a).
- README rewrite: 30-second pitch, screenshots, one-command install, system requirements.
- LICENSE (MIT or whatever repo settles on), CONTRIBUTING.md, docs/privacy.md (zero-telemetry statement).
- Clean-Mac VM dry run against the real release URL (Plan 08's deferred Task 10).
- Clean-Windows VM dry run against the real release URL (Plan 08's deferred Task 11).
- Full 104-item manual-QA sweep receipt (Q3a).
- 6–8 README screenshots captured during the sweep (Q4b).
- `plan-09-ship` + `v0.1.0` tags.

**Out of scope (deferred beyond v0.1.0):**
- Code signing (Mac notarization, Windows Authenticode) — v0.2.0+.
- Native bundles (Electron/Tauri/py2app) — roadmap.
- Auto-update without user intervention — `brain upgrade` stays manual.
- Linux-first install — best-effort only.
- Demo video (Q4c would be v0.2.0).
- App-store distribution.
- Multi-platform tarball split (Q1b) — revisit if airgap / corp-proxy friction surfaces.
- Telemetry of any kind (intentional; project principle).

---

## Decisions — Q1–Q4 (pinned)

- **Q1a** — One universal `brain-0.1.0.tar.gz` containing Python source, prebuilt `apps/brain_web/out/`, `uv.lock`, install scripts, README/LICENSE/VERSION. fnm + Node installed at install time (for future `brain upgrade`), pnpm via corepack.
- **Q2a** — `brain start` spawns a background thread that calls `check_latest_release()` with a 3s timeout. If newer version found, prints one-line nudge to stdout after the running-at banner. Opt-out `BRAIN_NO_UPDATE_CHECK=1` already honored.
- **Q3a** — Full 104-item `docs/testing/manual-qa.md` sweep. Lands as `docs/testing/v0.1.0-qa-receipt.md` (filled template) + screenshots under `docs/testing/screenshots/v0.1.0/`.
- **Q4b** — 6–8 README screenshots captured during the Q3a sweep. No video.

---

## Group 1 — Pre-release prep (Tasks 1–4)

### Task 1 — Version bump to 0.1.0

**Owning subagent:** brain-installer-engineer

**Goal:** pin `0.1.0` everywhere the version surfaces.

**Files:**
- Create: `VERSION` at repo root containing just `0.1.0\n`.
- Modify: `packages/brain_core/src/brain_core/__init__.py` — set `__version__ = "0.1.0"`.
- Modify: `packages/brain_core/pyproject.toml` — set `version = "0.1.0"`.
- Modify: `packages/brain_cli/pyproject.toml` — `version = "0.1.0"` + pin `brain_core==0.1.0`.
- Modify: `packages/brain_mcp/pyproject.toml` — same.
- Modify: `packages/brain_api/pyproject.toml` — same.
- Modify: `apps/brain_web/package.json` — `"version": "0.1.0"`.
- Modify: `pyproject.toml` (workspace root) if it carries a version.
- Modify: `packages/brain_cli/src/brain_cli/commands/doctor.py` — `check_ui_bundle` / any version comparison now expects `0.1.0`.
- Modify: `packages/brain_cli/src/brain_cli/runtime/release.py` — the current-version reader now reads from `VERSION` first, `brain_core.__version__` as fallback (already the order — just double-check).
- Create: `packages/brain_cli/tests/commands/test_version.py` — 3 tests: `brain --version` prints 0.1.0, `VERSION` file readable, `brain_core.__version__` matches.

**Process:**
1. Grep for current version sigil (likely `0.0.1` or similar): `rg -n '0\.0\.\d' pyproject.toml packages apps`.
2. Flip all hits. `uv sync --reinstall` to rebuild wheels with new version.
3. Write 3 version tests (red → green).
4. Run full suite: **930+16 Python, 224+1 frontend, 14/14 e2e** — unchanged plus 3 new.
5. Commit: `chore(release): bump version to 0.1.0`.

**Report:** Python count (expected 933+16), any version drift surfaced, commit hash.

---

### Task 2 — Known-issues triage

**Owning subagent:** brain-test-engineer

**Goal:** consolidate every "Task 25 sweep item" and deferred-decision across Plans 01–08 into one `docs/v0.1.0-known-issues.md` with triage tags: `BLOCKER` (must fix before v0.1.0 tag), `RELEASE_NOTE` (ship + mention in release notes + GH issue), `DEFER` (future release, no release-note mention).

**Files:**
- Create: `docs/v0.1.0-known-issues.md`.
- Sources to consolidate (read all):
  - `tasks/lessons.md` (Plan 01–08 sections)
  - `tasks/plans/02-ingestion.md` through `tasks/plans/08-install.md` Task-N reports + Review sections
  - Git log: `git log --oneline --all | rg -i 'deferred|task 25|known issue'` for surfaced items
  - Task 25A's sweep (commit `3c228a3`) left items; Plan 08 Task 12's close handed some to Plan 09.
- Triage table format:
  ```
  | # | Item | Source | Triage | Action |
  |---|------|--------|--------|--------|
  | 1 | Monaco lazy-prefetch on Edit hover | Plan 07 Task 18 | DEFER | v0.2.0 |
  | 2 | Ingest `new_files=[]` scope-guard in E2E mode | Plan 08 Task 12 | RELEASE_NOTE | open GH issue; document in v0.1.0 notes |
  ```

**Process:**
1. Audit each plan's Review + lessons section.
2. Categorize every outstanding item.
3. For each `BLOCKER`: open a GitHub issue and either fix it in Plan 09 (add a Task) or downgrade to `RELEASE_NOTE` with justification.
4. For `RELEASE_NOTE`: queue for Task 3's CHANGELOG.
5. For `DEFER`: list in `docs/v0.1.0-known-issues.md` but nowhere user-facing.

**Expected output:** 25–40 items, most `DEFER`, ~3–5 `RELEASE_NOTE`, ideally 0 `BLOCKER` (if BLOCKERs surface, flag early — may require adding a Task 2b patch).

**Commit:** `docs(release): triage plan 01–08 sweep items for v0.1.0`.

---

### Task 3 — CHANGELOG.md + release-notes-v0.1.0.md

**Owning subagent:** brain-test-engineer

**Goal:** author the first CHANGELOG.md (Keep-a-Changelog format) and a standalone release-notes-v0.1.0.md for the GitHub release body.

**Files:**
- Create: `CHANGELOG.md` at repo root (Keep-a-Changelog format). Sections: Added / Changed / Fixed / Removed / Security. Initial entry for `[0.1.0] — 2026-04-XX` built from `git log plan-01-foundation..HEAD` grouped by plan (not by date).
- Create: `docs/release-notes/v0.1.0.md` — user-facing release notes. Sections:
  - What's new (4–6 headline bullets — LLM-maintained knowledge base, chat/brainstorm/draft, Obsidian-compatible vault, install on Mac+Windows).
  - Install: link to README.
  - System requirements: macOS 13+, Windows 11.
  - Known issues: every `RELEASE_NOTE`-triaged item from Task 2 with GH issue link.
  - Links: spec, roadmap, contributing.

**Process:**
1. `git log plan-01-foundation..HEAD --format='%s' | rg -v '^docs:|^Merge '` → generate the raw change list.
2. Group under Added / Changed / Fixed by commit-message verb.
3. Write release notes targeting the non-technical user.
4. Commit: `docs(release): CHANGELOG + v0.1.0 release notes`.

---

### Task 4 — `brain start` update-check nudge

**Owning subagent:** brain-installer-engineer

**Goal:** Q2a — background update-check in `brain start` that prints a one-line nudge if a newer version exists.

**Files:**
- Modify: `packages/brain_cli/src/brain_cli/commands/start.py` — after the `brain running at ...` print, spawn a daemon `threading.Thread` that calls `check_latest_release(current_version, timeout_s=3)`. On success and newer version: `print(f"A newer version is available: v{current} → v{latest}. Run 'brain upgrade' to update.")`. On timeout / network error / already-latest / `BRAIN_NO_UPDATE_CHECK=1`: silent.
- Modify: `packages/brain_cli/src/brain_cli/runtime/release.py` — if not already, add `timeout_s` keyword to `check_latest_release`. Return `None` on exception so caller doesn't need try/except.
- Create: `packages/brain_cli/tests/commands/test_start_update_check.py` — 4 tests:
  - (a) Newer version → nudge printed.
  - (b) Same version → no nudge.
  - (c) Timeout → no nudge, no crash.
  - (d) `BRAIN_NO_UPDATE_CHECK=1` → check_latest_release never called.

**Context:**
- `check_latest_release` was added in Plan 08 Task 5 (commit `d802f93`). Reuse it — don't reimplement.
- The thread must be daemon (`Thread(target=..., daemon=True)`) so it doesn't hold the process open on `brain start` exit. Although start typically stays running to supervise, daemon still recommended for safety.
- The nudge is print-to-stdout; no buffering issues since it's at the end of the start command's output phase.
- Fire-and-forget — `start` doesn't wait for the thread.

**Process:**
1. Write 4 tests (red).
2. Implement the thread spawn.
3. Verify full suite: **937+16 Python** (933 after Task 1 + 4 new).
4. Commit: `feat(cli): plan 09 task 4 — brain start update-check nudge (Q2a)`.

---

## Group 2 — Docs polish (Tasks 5–6)

### Task 5 — README.md rewrite + quickstart

**Owning subagent:** main loop or brain-prompt-engineer

**Goal:** README becomes the landing page — pitch, install command, one ingest + chat example, links to spec + docs + support.

**Files:**
- Modify: `README.md` (replace existing). Sections:
  1. One-line pitch + GIF/screenshot (Task 12 fills the screenshot).
  2. What it is (3-sentence paragraph).
  3. Install (copy-paste command per platform). Placeholder for GitHub release URL — Task 8 fills it in.
  4. Quickstart: `brain start` → setup wizard → first chat turn.
  5. Screenshots (6–8 placeholders — Task 12 fills).
  6. System requirements.
  7. Links: spec, lessons, CHANGELOG, license, privacy, contributing.
  8. Status + roadmap (note: v0.1.0 first release; see `docs/release-notes/v0.1.0.md`).

**Process:**
1. Draft README.
2. Link-check all internal references.
3. Commit: `docs(readme): v0.1.0 README rewrite (placeholder screenshots + install URL)`.

---

### Task 6 — LICENSE + CONTRIBUTING.md + docs/privacy.md

**Owning subagent:** main loop or brain-prompt-engineer

**Goal:** top-level licensing + contribution process + privacy statement.

**Files:**
- Create: `LICENSE` — MIT (or whatever the user picks — confirm in-loop before committing). If no signal: default MIT.
- Create: `CONTRIBUTING.md` — covers: dev setup, `uv sync`, tests, plan-based workflow reference, superpowers skill notes, PR guidelines, the "vault is sacred" rule.
- Create: `docs/privacy.md` — zero-telemetry statement: no analytics, no crash reporting, no phone-home except opt-out update-check (Task 4). Local-first data. Token file permissions. Secrets never leave disk. Explicit "what brain does NOT do" list.

**Process:**
1. Ask main loop if MIT is OK (default assume yes).
2. Write the three docs.
3. Commit: `docs: add LICENSE + CONTRIBUTING + privacy`.

---

## Group 3 — Real GitHub release (Tasks 7–8)

### Task 7 — scripts/release.sh (universal tarball builder)

**Owning subagent:** brain-installer-engineer

**Goal:** `scripts/release.sh` produces `release/brain-0.1.0.tar.gz` + `release/brain-0.1.0.tar.gz.sha256` from a clean HEAD.

**Files:**
- Create: `scripts/release.sh` — bash. Flow:
  1. `git status --porcelain` → if dirty, require `--force` or abort with message.
  2. Read version from `VERSION` file.
  3. Build UI: `pnpm -F brain_web install && pnpm -F brain_web build`. Verify `apps/brain_web/out/index.html` exists.
  4. Create staging dir `release/staging-<version>/brain-<version>/`.
  5. Copy files: `packages/` (source only, no `__pycache__`, no `.venv/`), `apps/brain_web/` (SANS `node_modules/` + `.next/`, KEEP `out/`), `scripts/install*`, `scripts/install_lib/`, `pyproject.toml`, `uv.lock`, `VERSION`, `README.md`, `LICENSE`, `CHANGELOG.md`, `docs/release-notes/v<version>.md`, `assets/`.
  6. Explicitly EXCLUDE: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `tasks/`, `docs/superpowers/`, `docs/design/`, `.claude/`, `.brain/`, `scripts/tests/`, `packages/*/tests/`, `apps/brain_web/tests/`, `release/` itself, any hidden dotfile not explicitly included.
  7. Tarball: `tar -czf release/brain-<version>.tar.gz -C release/staging-<version> brain-<version>`.
  8. SHA256: `shasum -a 256 release/brain-<version>.tar.gz > release/brain-<version>.tar.gz.sha256`.
  9. Print summary: tarball size, SHA, file count, top-level tree.
- Create: `scripts/tests/test_release_sh.py` — 3 Python tests:
  - (a) Happy path: run release.sh against a tmp HEAD, verify tarball contents match the expected include/exclude lists.
  - (b) Dirty tree without `--force` aborts.
  - (c) Tarball extract → install.sh works (integration: extract + run install.sh in tmpdir + `brain --version` returns 0.1.0).

**Context:**
- Uses `git archive HEAD` as the basis OR manual rsync with explicit includes — prefer `git archive --prefix=brain-<version>/ --format=tar HEAD | gzip` for reproducibility, then supplement with the prebuilt `apps/brain_web/out/` copied in (git archive uses working-tree-known files; `out/` is usually gitignored).
- Target tarball size: ~15–25MB (Python source small; `out/` is ~3MB; no node_modules).

**Process:**
1. Read `scripts/cut-local-tarball.sh` for the git-archive pattern.
2. Extend into `scripts/release.sh` with the full include/exclude discipline.
3. Write + pass the 3 tests.
4. Run release.sh locally, inspect output.
5. Commit: `feat(release): plan 09 task 7 — scripts/release.sh (universal tarball builder)`.

---

### Task 8 — Cut v0.1.0 on GitHub + flip install URLs

**Owning subagent:** brain-installer-engineer + main loop

**Goal:** create the GitHub release, upload the tarball, flip install.sh/install.ps1 default `BRAIN_RELEASE_URL` from placeholder to the real URL, regression-test.

**Files:**
- Modify: `scripts/install.sh` — change the default tarball URL constant from placeholder to `https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/brain-0.1.0.tar.gz`.
- Modify: `scripts/install.ps1` — same flip.
- Modify: `scripts/install_lib/fetch_tarball.sh` / `.ps1` — if any default URL hardcoded there, sync.
- Modify: `packages/brain_cli/src/brain_cli/runtime/release.py` — ensure `check_latest_release` points at the real repo for the GH API endpoint (should already be `https://api.github.com/repos/ToTo-LLC/cj-llm-kb/releases/latest` per Plan 08).

**Process:**
1. Pre-flight: run `scripts/release.sh` to produce `release/brain-0.1.0.tar.gz` + SHA.
2. Verify SHA locally.
3. **Main loop** (manual step with user confirm): `gh release create v0.1.0 --title "brain 0.1.0" --notes-file docs/release-notes/v0.1.0.md release/brain-0.1.0.tar.gz release/brain-0.1.0.tar.gz.sha256`.
4. Verify the release is public + asset URLs are the expected pattern.
5. Flip install-script URLs.
6. Re-run `scripts/demo-plan-08.py` (updated to use the real URL if envvar not set) OR a smaller regression: `BRAIN_RELEASE_URL=https://.../brain-0.1.0.tar.gz bash scripts/install.sh` against a tmp HOME-like dir → `brain doctor` green.
7. Commit: `feat(release): plan 09 task 8 — cut v0.1.0 GitHub release + flip install default URLs`.

---

## Group 4 — Clean-VM dry runs (Tasks 9–10)

### Task 9 — Clean-Mac VM dry run against real v0.1.0

**Owning subagent:** brain-test-engineer (user-driven via Plan 08 harness)

**Goal:** execute Plan 08's deferred Task 10 using the Plan 08 harness, but pointed at the real GitHub release URL.

**Process (user-driven):**
1. User boots a fresh Mac 14 VM (Tart / UTM).
2. In VM: `curl -fsSL https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/install.sh | bash` (or curl install.sh from repo if uploaded as separate asset).
3. Walk install → `brain doctor` → `brain start` → setup wizard → one ingest → approve → `brain stop` → `brain uninstall`.
4. Capture screenshots per `docs/testing/clean-mac-vm-host-instructions.md`.
5. Paste output + screenshots into `docs/testing/clean-mac-vm-receipt.md` (Plan 08 template).
6. Commit receipt: `test(release): plan 09 task 9 — clean-Mac VM dry run receipt (v0.1.0)`.

**Hard gate:** receipt status `✓ PASS` or `⚠ PASS WITH NOTES`. Any FAIL blocks v0.1.0 tag — loop back to fix.

---

### Task 10 — Clean-Windows VM dry run against real v0.1.0

**Owning subagent:** brain-test-engineer (user-driven)

**Goal:** same as Task 9 but Windows 11 VM via UTM / Parallels using `install.ps1`.

**Process:** mirror Task 9 using `docs/testing/clean-windows-vm-host-instructions.md` + `clean-windows-vm-receipt.md`.

**Hard gate:** receipt `✓ PASS` or `⚠ PASS WITH NOTES`.

---

## Group 5 — Final QA + ship (Tasks 11–13)

### Task 11 — Full 104-item manual-QA sweep (Q3a)

**Owning subagent:** brain-test-engineer (user-driven)

**Goal:** walk the full `docs/testing/manual-qa.md` checklist on the primary machine, installed from v0.1.0 release. Capture 6–8 screenshots during the sweep for README (Q4b).

**Files:**
- Create: `docs/testing/v0.1.0-qa-receipt.md` — per-section status + findings.
- Create: `docs/testing/screenshots/v0.1.0/` — 6–8 captured screenshots with descriptive filenames (setup-wizard-step-3.png, chat-first-response.png, pending-diff.png, browse-backlinks.png, settings-domains.png, inbox-drag-drop.png, bulk-dry-run.png).

**Process:**
1. Install v0.1.0 on primary machine via `curl ... | bash` from the real GitHub release.
2. Walk all 104 items in `manual-qa.md`. Mark each `✓ PASS`, `⚠ PASS WITH NOTES`, or `✗ FAIL`.
3. Capture screenshots at 6–8 natural moments during the walk.
4. Fill `v0.1.0-qa-receipt.md` with per-section summary + findings list.
5. Any `✗ FAIL` → fix inline (commit with `fix(...)` prefix) or triage to `docs/v0.1.0-known-issues.md` as `RELEASE_NOTE`. Loop back through the failing item after fix.
6. Commit: `test(release): plan 09 task 11 — v0.1.0 full QA sweep receipt`.

**Hard gate:** receipt overall status `✓ PASS`, all FAIL items resolved or triaged to known issues.

---

### Task 12 — Embed screenshots in README + doc polish from QA findings

**Owning subagent:** main loop

**Goal:** flip README's screenshot placeholders to real images captured in Task 11; fold any doc fixes surfaced during QA.

**Files:**
- Modify: `README.md` — replace screenshot placeholders with `![setup wizard](docs/testing/screenshots/v0.1.0/setup-wizard-step-3.png)` etc. Tight captions.
- Modify: any doc that Task 11 surfaced as stale (CONTRIBUTING command lines that don't match the installed CLI, etc.).

**Commit:** `docs(readme): embed v0.1.0 screenshots + address QA doc fixes`.

---

### Task 13 — Tag v0.1.0 + plan-09-ship + close + lessons

**Owning subagent:** brain-test-engineer + main loop

**Goal:** final gates, tag, push.

**Process:**
1. Run all tests: `uv run pytest packages/ scripts/ -q` + `pnpm -F brain_web test --run` + `pnpm -F brain_web exec playwright test`. All green.
2. Run `uv run python scripts/demo-plan-09.py` (write this script — mirror demo-plan-08.py + add Task 4 update-check verification + Task 1 version assertion). Must print `PLAN 09 DEMO OK` on exit 0.
3. Update `tasks/todo.md` — flip Plan 09 row to ✅ with date 2026-04-XX + tag `plan-09-ship`.
4. Append `### Plan 09 — Ship v0.1.0` section to `tasks/lessons.md` covering: completion stats, release-pipeline retrospective, VM dry-run findings, manual-QA findings, handoff to v0.2.0 (icons, update check UX polish, PDF upload, demo video).
5. Append `## Review` section to `tasks/plans/09-ship.md` per Plan 07/08 template.
6. Close commit: `docs: close plan 09 (ship) — tag plan-09-ship + v0.1.0`.
7. Tags: `git tag plan-09-ship` + `git tag v0.1.0`.
8. Main loop pushes main + both tags to origin.

---

## Review

_To be appended by Task 13._
