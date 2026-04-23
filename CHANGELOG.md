# Changelog

All notable changes to brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-04-23

Initial public release. Eight implementation plans (foundation, ingestion,
chat, MCP server, REST/WebSocket API, frontend, install + packaging, ship)
landed between 2026-04-13 and 2026-04-23 on `main` under the
`plan-01-foundation` through `plan-08-install` tags.

### Added

- **LLM-maintained knowledge vault.** Obsidian-compatible Markdown with YAML
  frontmatter and `[[wikilinks]]`, stored at `~/Documents/brain/`.
  Domain-scoped folders (`research`, `work`, `personal`) with a per-thread
  active scope; `personal` content never leaks into wildcard or default
  queries. Every vault mutation goes through `VaultWriter` with atomic
  temp-plus-rename writes and a per-operation undo log.

- **Nine-stage ingestion pipeline.** Classify, fetch, extract, archive,
  route, summarize, integrate, apply, log/cost. Day-one handlers for plain
  text and Markdown, web URLs (via `trafilatura`), PDFs (via `pymupdf`),
  pasted emails, meeting transcripts (`.txt`, `.vtt`, `.srt`, `.docx`), and
  single tweets by URL. Idempotent (content-hash de-dup), resumable,
  per-source failure isolation. Bulk import walks a folder, generates a
  dry-run patch tree under `.brain/migrations/<timestamp>/`, then applies
  on confirmation.

- **Three chat modes.** **Ask** for cited synthesis with refusal-to-
  speculate, **Brainstorm** for adversarial co-development with Socratic
  pushback, **Draft** for inline document edits via structured
  ` ```edits ` fences. Per-mode model selection, per-turn context
  compilation from `BRAIN.md` + `index.md` + explicit reads, and a
  configurable hard context cap with oldest-turn trimming. Threads persist
  as Markdown in `chats/<domain>/` with `state.sqlite` as a derived cache;
  auto-titled after turn 2.

- **Thirty-four-tool LLM surface.** Read (`brain_search`, `brain_read_note`,
  `brain_get_index`, `brain_recent`, `brain_get_brain_md`,
  `brain_list_domains`), ingest (`brain_ingest`, `brain_classify`,
  `brain_bulk_import`), patches (`brain_list_pending_patches`,
  `brain_apply_patch`, `brain_reject_patch`, `brain_undo_last`,
  `brain_get_pending_patch`, `brain_propose_note`), maintenance
  (`brain_lint`, `brain_cost_report`, `brain_config_get`,
  `brain_config_set`, `brain_fork_thread`), and sweep-added tools for
  Claude Desktop (`brain_mcp_install`, `brain_mcp_uninstall`,
  `brain_mcp_status`, `brain_mcp_selftest`), provider management
  (`brain_set_api_key`, `brain_ping_llm`), backups (`brain_backup_create`,
  `brain_backup_list`, `brain_backup_restore`), and domain lifecycle
  (`brain_delete_domain`). Exposed identically over REST (`brain_api`),
  stdio MCP (`brain_mcp`), and the web app.

- **Next.js 15 web app.** Six-step setup wizard, chat transcript with
  streaming tokens + tool-call cards + inline patch proposals, Inbox with
  drop-zone, Browse with Monaco editor and Obsidian hand-off, Pending
  changes with diff view and bulk approve, Bulk import 4-step flow,
  eight-panel Settings (General / Providers / Budget / Autonomous /
  Integrations / Domains / BRAIN.md editor / Backups). Light + dark
  themes. WCAG 2.2 AA accessibility (axe-core gates in CI).

- **One-command install on Mac and Windows.** Universal `brain-0.1.0.tar.gz`
  served from the GitHub release. `install.sh` (macOS 13+) and
  `install.ps1` (Windows 11) bootstrap `uv` + `fnm` + Node, stage the
  install under `~/.local/share/brain/`, and put a `brain` shim on the
  user's PATH. Ships a `.app` launcher on macOS and a Start Menu entry
  on Windows. `brain doctor` runs ten diagnostic checks (vault writable,
  Python/Node present, API key valid, ports free, etc.) with plain-
  English remediation for each.

- **Patch safety rails.** Every LLM-originated vault write is a typed
  patch set (`new_files`, `edits`, `index_entries`, `log_entry`) validated
  before apply. The autonomous-mode toggle only changes whether the
  approval queue auto-approves — the tool surface and validation path
  are identical. Per-patch 50-file / 500-KB ceilings, per-session rate
  limiting on patches/min and tokens/min, and a typed-confirm barrier on
  every destructive action (`brain uninstall`, `brain_delete_domain`,
  backup restore). Rollback via `brain_undo_last` or the undo banner in
  the web UI.

### Changed

- Initial release — nothing changed from a prior version.

### Fixed

- Initial release — nothing to fix.

### Security

- Loopback-only HTTP and WebSocket binding. Same-origin + per-run token
  gate on every REST call; DNS-rebinding protection in middleware.
- Secrets (Anthropic API key, API token) stored with `0600` permissions
  on Unix; a read-only-bit fallback on Windows (see Known issues in the
  v0.1.0 release notes).
- Zero telemetry and zero analytics. The only outbound non-LLM call is
  an opt-out GitHub version check in `brain start` (set
  `BRAIN_NO_UPDATE_CHECK=1` to disable).
- LLM prompt and response bodies are not logged unless
  `log_llm_payloads = true` is explicitly set.

[Unreleased]: https://github.com/ToTo-LLC/cj-llm-kb/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ToTo-LLC/cj-llm-kb/releases/tag/v0.1.0
