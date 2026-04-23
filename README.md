# brain

**A knowledge base you run on your own machine, maintained by an LLM.**

brain turns a folder of Markdown files into a second brain you can chat with, brainstorm against, and draft inside. It's [Obsidian](https://obsidian.md)-compatible, keeps every change staged for your approval, and runs entirely on your laptop — the only outbound calls are the LLM API calls you configure.

> **v0.1.0** — first public release. See the [release notes](docs/release-notes/v0.1.0.md).

![brain chat screen](docs/testing/screenshots/v0.1.0/chat-first-response.png)

*Screenshot placeholder — real image lands in [Plan 09 Task 12](tasks/plans/09-ship.md#task-12--embed-screenshots--doc-polish-from-qa-findings).*

---

## What it is

A Python + TypeScript monorepo that turns `~/Documents/brain/` into an LLM-maintained wiki. The vault is plain Markdown with YAML frontmatter — point Obsidian at the same folder if you want. brain ingests sources (URLs, PDFs, meeting transcripts, pasted text), classifies them into domains (`research` / `work` / `personal`), proposes notes + cross-links as a typed patch set, and waits for you to approve before anything touches disk.

Three ways to work with it:

- **Ask** — synthesis with citations. "What has the vault said this year about silent-buyer patterns?"
- **Brainstorm** — adversarial co-development. "Argue with me about compounding curiosity as a meta-practice."
- **Draft** — inline document edits. brain proposes `\`\`\`edits` blocks that highlight in the live document; you review + apply.

Every vault mutation goes through a write barrier with atomic temp+rename, an undo log per operation, and typed confirmation on destructive actions. `personal`-scoped content never surfaces in default queries.

---

## Install

### macOS 13+

```bash
curl -fsSL https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/install.sh | bash
```

### Windows 11

```powershell
irm https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/install.ps1 | iex
```

No sudo, no admin, no system Python required. The install script drops the app at `~/Applications/brain/` (Mac) or `%LOCALAPPDATA%\brain\` (Windows), puts `brain` on PATH, and runs `brain doctor` to confirm everything works.

### What gets installed

- **Python app** (~30MB) — the backend, CLI, and setup wizard.
- **Prebuilt web UI** (~3MB) — served from the backend; no Node runtime needed at rest.
- **uv** — Python package manager (skipped if already present).
- **fnm + Node 20** (~100MB) — kept around for future `brain upgrade`; not on your global PATH.

Total install time: ~30 seconds on a warm network.

---

## Quickstart

```bash
brain start
```

Opens your default browser at `http://localhost:4317/`. Walk the 6-step setup wizard:

1. **Welcome.** What brain is, what it isn't.
2. **Vault location.** Default `~/Documents/brain/`.
3. **LLM provider.** Paste an Anthropic API key ([get one](https://console.anthropic.com)).
4. **Starting theme.** Research / Work / Personal / Blank.
5. **BRAIN.md.** Optional — brain's system prompt lives here.
6. **Claude Desktop integration.** Optional MCP install.

Then start chatting. Your first message becomes the thread title.

---

## System requirements

- **macOS 13+** (Apple Silicon or Intel) or **Windows 11**
- ~500MB free disk for the app; your vault grows with your notes
- An **Anthropic API key** — get one at https://console.anthropic.com
- A browser (Chrome, Safari, Edge, or any Chromium-based — Firefox best-effort)

Linux is best-effort — `install.sh` works on most distros but isn't gate-tested for v0.1.0.

---

## Screenshots

*(placeholders — real images land after Plan 09 Task 11 manual-QA sweep)*

- ![setup wizard step 3](docs/testing/screenshots/v0.1.0/setup-wizard-step-3.png) — setup wizard (API key step)
- ![new thread empty](docs/testing/screenshots/v0.1.0/new-thread-empty.png) — starter prompts per chat mode
- ![pending patch](docs/testing/screenshots/v0.1.0/pending-patch-diff.png) — pending patch with inline diff
- ![browse backlinks](docs/testing/screenshots/v0.1.0/browse-backlinks.png) — browse view with backlinks rail
- ![settings domains](docs/testing/screenshots/v0.1.0/settings-domains.png) — domain settings
- ![bulk import](docs/testing/screenshots/v0.1.0/bulk-dry-run.png) — bulk import dry-run table

---

## Daily commands

| Command | What it does |
|---|---|
| `brain start` | Launches backend + opens browser. |
| `brain stop` | Stops the daemon. |
| `brain status` | Shows running state + URL + uptime. |
| `brain doctor` | Diagnostic with plain-English fixes. |
| `brain backup` | Manual vault snapshot. |
| `brain upgrade` | Checks GitHub for a newer release; atomic swap with rollback. |
| `brain uninstall` | Typed-confirm removal. Vault preserved by default. |

---

## Architecture

A pure-Python `brain_core` package owns all logic (vault I/O, ingestion, LLM abstraction, chat, lint, cost tracking, config) and has zero web dependencies. Three thin wrappers import it:

- `brain_cli` — Typer CLI
- `brain_mcp` — MCP server (Claude Desktop integration)
- `brain_api` — FastAPI REST + WebSocket + static UI host

The web app (`brain_web`) is a Next.js 15 static export served by `brain_api`. One runtime on your box (Python) serves both the UI and the API on a single port. See [the spec](docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md) for details.

---

## Non-negotiable principles

- **The vault is sacred.** Every mutation goes through `VaultWriter`. Writes are atomic. Uninstall never deletes the vault without typed confirmation.
- **LLM writes are always staged.** The LLM produces typed patch sets; patches validate before apply. Autonomous-mode only changes whether the approval queue auto-approves.
- **Zero telemetry.** No analytics, no crash reporting, no phone-home. The only outbound non-LLM call is an opt-out update check on `brain start`.
- **Privacy first.** `personal`-scoped content never surfaces in default or wildcard queries. Secrets live in `.brain/secrets.env` (chmod 600 on Unix, ACL-restricted on Windows). Never logged.
- **Cross-platform from day one.** Mac 13+ and Windows 11 are first class.

---

## Links

- [Design document](docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md) — the full spec
- [CHANGELOG](CHANGELOG.md)
- [Release notes — v0.1.0](docs/release-notes/v0.1.0.md)
- [Known issues in 0.1.0](docs/v0.1.0-known-issues.md)
- [Privacy](docs/privacy.md) *(coming in Plan 09 Task 6)*
- [Contributing](CONTRIBUTING.md) *(coming in Plan 09 Task 6)*
- [License](LICENSE) *(coming in Plan 09 Task 6)*

---

## Status

**v0.1.0** — first public release. See [release notes](docs/release-notes/v0.1.0.md) for the headline features and known issues.

Found a bug or have feedback? [Open an issue](https://github.com/ToTo-LLC/cj-llm-kb/issues).
