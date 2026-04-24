# brain

**A knowledge base that grows with you — and stays yours.**

---

## The problem

Your knowledge tools have a split personality.

The "note-taking" half — Obsidian, Apple Notes, Notion, a folder of Markdown — is where you actually *own* your thinking. It's searchable, portable, durable. It survives the company that made it. But it's inert. Notes sit there until you dig them up. Connections between ideas happen only when you remember to make them.

The "AI assistant" half — ChatGPT, Claude, Cursor — is where the synthesis happens. It can summarize, connect, argue with you, rewrite. But it doesn't know what you've already written. It doesn't remember what you said three weeks ago. And whatever you tell it is a one-way deposit: into their servers, their training data, their retention policies. The more useful it becomes, the less it feels like yours.

brain collapses the two halves.

---

## What it is

brain is a knowledge base you run on your own machine, maintained by an LLM. You give it a folder. You tell it what to remember. It reads, classifies, summarizes, and files the things you care about — as plain Markdown files with YAML frontmatter and `[[wikilinks]]`. You can chat with it, brainstorm against it, draft inside it. Everything the LLM proposes is staged for your approval before it touches disk. Nothing leaves your computer except the LLM API calls *you* configure.

Point [Obsidian](https://obsidian.md) at the same folder if you want. brain won't fight you. The vault is a filesystem, not a database. If brain disappears tomorrow, your notes survive because they never stopped being plain files.

The pattern was popularized by Andrej Karpathy as the "LLM wiki" — a second brain maintained by a first brain. brain is an opinionated, shippable, local-first take on that idea.

---

## What it feels like to use

brain has three modes, one for each mental motion most knowledge workers actually do.

### Ask — synthesis with citations

You type:

> *"What has the vault said this year about silent-buyer patterns?"*

brain searches your notes, pulls the three most relevant, cross-references two concept files, and composes a short synthesis with `[[wikilinks]]` back to the source material. Every claim cites a file. Every citation is a real line you can click through to read in context. If your notes don't have an answer, it tells you so plainly instead of making one up.

Think: a research assistant who has read every note you've ever written and never forgets which one said what.

### Brainstorm — adversarial co-development

You type:

> *"Argue with me about compounding curiosity as a meta-practice."*

brain takes the opposing position, pressure-tests your reasoning, proposes three angles you haven't considered, and flags where your own prior notes disagree with themselves. It's not a validator. It's not a cheerleader. It's the friend who reads your drafts and asks *but have you thought about —?*

Think: the smartest colleague on your team, but available at 2 AM, with total recall.

### Draft — inline document edits

You open a document in the vault. You type:

> *"Rewrite the intro for a non-expert reader."*

brain proposes inline edits — actual word-level changes, highlighted in the live document. You see what it wants to change before it changes anything. You approve the edits you like, reject the ones you don't. Nothing touches disk until you say so.

Think: a copy editor who works at the speed of thought but never overrides your voice without permission.

---

## What makes it different

### 1. Your vault is yours. Forever.

The vault is `~/Documents/brain/` — a regular folder of Markdown files. Open it in Finder. Open it in Obsidian. Open it in `vim`. Commit it to a git repo of your own. Sync it through Dropbox if you want. When brain writes, it writes plain text with YAML frontmatter and `[[wikilinks]]` — the format you'd use yourself if you were doing it by hand.

If brain shuts down tomorrow, you don't lose your knowledge. You lose the assistant. The knowledge is already on your disk in a format every tool in the world can read.

### 2. Every change is staged. You're always in the loop.

The LLM doesn't get write access to your vault. It gets write access to a *pending patch queue*. Every proposed note, every edit, every wikilink addition lands in a queue you review — with a diff, a reason, and one-click approve/edit/reject.

You can flip individual categories to auto-apply (source ingest, entity updates, concept notes) once you trust them. Index rewrites stay manual-by-default with a visible warning before you enable automation — because letting an LLM rewrite your domain indexes without review is the kind of decision you want to make consciously.

The system is built so the LLM can never:
- Delete a file without a typed confirmation ("type `DELETE-VAULT` to permanently remove all your notes")
- Bypass your domain scope (the `personal` domain never surfaces in default queries)
- Exceed your budget (hard dollar caps stop all LLM calls; no soft warnings)
- Log your prompt or response bodies (opt-in via `log_llm_payloads=true` only)

### 3. One runtime. Truly local.

Most "AI-powered" tools sit on top of an SDK from an AI company plus a backend service they operate. Your data moves through at least two middlemen before it reaches the model.

brain is different. `brain start` launches one Python process on your machine. That process serves the web UI, the REST API, the WebSocket stream, and the MCP server — all on `localhost:4317`. When you ask the LLM a question, your browser talks to that local process, which makes a direct HTTPS call to your chosen API provider (Anthropic for v0.1.0). No intermediary backend. No account. No cloud sync. No telemetry. No analytics. Not even crash reporting.

The only outbound non-LLM calls brain ever makes:

- **The LLM API calls you configure.** Your prompts go from your machine to Anthropic. That's between you and Anthropic.
- **An opt-out update check** on `brain start` — one `GET api.github.com/repos/.../releases/latest`, no identifying headers. Disable with `BRAIN_NO_UPDATE_CHECK=1`.
- **Tarball downloads** when you run `brain upgrade`, if a new version exists.

That's it. You can verify it with `tcpdump` on any network.

### 4. Three modes, one discipline

Ask / Brainstorm / Draft aren't marketing categories. They're separate system prompts with separate tool policies and — if you want — separate LLM models. You can run Ask on Haiku for speed, Brainstorm on Sonnet for depth, Draft on Opus for care. Per-mode cost tracking is built in so you see exactly where your LLM spend goes.

The modes share a single memory: your vault. A thread you started in Ask can fork to Brainstorm at any turn. Any mode can propose a note filing or an inline edit. The modes are lenses, not silos.

### 5. MCP-native. Talk to it from any Claude.

brain ships a Model Context Protocol server out of the box. One command during setup wires it into Claude Desktop. Any conversation in Claude Desktop can read your vault, search your notes, propose patches, and approve them — same safety rails, same scope guards, same cost tracking. The 34 tools brain exposes (search, read, propose, apply, reject, ingest, ...) are available to Claude Desktop the moment you install.

You don't have to pick between "talk to the LLM in a nice UI" and "talk to the LLM from your preferred chat client." You get both. If you live in Claude Desktop, brain meets you there. If you live in the web UI, brain is there too. If you live in the terminal, `brain chat` is there too. Same vault, same patch queue, same knowledge.

### 6. Obsidian-friendly by design

The wiki format is the same format Obsidian uses: Markdown + YAML frontmatter + `[[wikilinks]]`. Point Obsidian at `~/Documents/brain/` and everything Just Works — backlinks, graph view, templates, the whole Obsidian ecosystem. brain becomes the LLM layer on top of your existing Obsidian workflow.

Or flip it: keep brain as the primary UI and never touch Obsidian. The vault doesn't care. It's plain text.

---

## How it works

brain is a Python + TypeScript monorepo. At runtime, one Python process (`brain_api`) serves four surfaces:

```
┌────────────────────────────────────────────────────────────┐
│                   brain_api (uvicorn, :4317)               │
│                                                            │
│   REST /api/*    ──┬──►  34-tool surface                   │
│   WebSocket /ws/*  ├──►  chat streaming, patch events      │
│   Static /        ─┴──►  Next.js SPA (brain_web)           │
│                                                            │
│                   ▲                                        │
│                   │ imports                                │
│                   │                                        │
│                brain_core                                  │
│   ┌─────────────────────────────────────────┐              │
│   │   vault I/O · ingest · LLM abstraction  │              │
│   │   chat · lint · cost · config · scope   │              │
│   └─────────────────────────────────────────┘              │
│                   ▲                                        │
│                   │ imports                                │
│                   │                                        │
│         ┌─────────┼─────────┐                              │
│         │         │         │                              │
│     brain_cli  brain_mcp  (your tests)                     │
└────────────────────────────────────────────────────────────┘
```

The core library (`brain_core`) has zero web dependencies. It's where the vault writer, the ingest pipeline, the LLM provider abstraction, the chat loop, the lint checks, the cost ledger, and the scope guard live. Everything — the CLI, the MCP server, the REST API — is a thin wrapper over it.

**Ingest pipeline (9 stages):**

1. **Claim** the source (dedup by content hash — safe to re-run on the same URL).
2. **Extract** text. Handlers for: `.txt`, `.md`, URLs (via `trafilatura`), PDFs (via `pymupdf`), `.vtt` / `.srt` / `.docx` meeting transcripts, raw-text email, X/Twitter archive exports.
3. **Classify** into `research` / `work` / `personal` via a small LLM call. Confidence threshold triggers human review.
4. **Summarize** to a ~200-word abstract.
5. **Integrate** — the LLM proposes a typed patch set: new files to create, existing files to edit, index entries to add, a log entry to write.
6. **Validate** — patches run through scope guard, wikilink resolver, frontmatter validator.
7. **Stage** — the patch lands in the pending queue.
8. **Review** — human or autonomous mode.
9. **Apply** — atomic temp-and-rename write, with an undo log record so you can revert.

The pipeline is resumable. If step 3 fails, you retry from step 3 — not the whole thing. LLM calls are cached by content hash. Nothing re-charges.

**Patch discipline:**

Every vault mutation goes through a single choke point (`VaultWriter`). Writes are atomic. Every applied change is recorded in an undo log. The only "delete" path is typed-confirmation with the literal word `DELETE-VAULT` or `UNINSTALL`. The vault is sacred — even uninstall defaults to *keep the vault*.

**Scope guard:**

Every vault read and every vault write passes through a function that enforces the user's current domain scope. There is no code path that bypasses it. Turn off `personal` domain in your scope picker, and the LLM can't see, search, or reference any note in `personal/*` until you turn it back on. This is a built-in privacy rail — not a setting you can forget to check.

**Cost + budget:**

Every LLM call writes a row to `costs.sqlite`: operation, model, tokens in / out, dollar cost, domain. Budget caps are hard stops. Hit your daily cap → all LLM calls pause until you raise it or wait for the day to roll over. You always know what you're spending. You never get a surprise bill.

---

## What it isn't

Honest positioning, because you're smart enough to tell.

- **Not a Notion/Obsidian replacement.** It's an LLM layer on top of the vault you already have (or the one it creates for you). If you love your current note-taking tool, keep using it — just point brain at the same folder.
- **Not a cloud SaaS.** There's no account, no subscription, no dashboard. You pay Anthropic (or whichever LLM provider you configure) for API use. That's the only recurring cost.
- **Not a "team" tool.** v0.1.0 is single-user. Collaboration / multi-user is a later-version decision. The vault is yours — sharing is intentionally not frictionless.
- **Not a research agent.** brain doesn't autonomously crawl the web. It ingests the specific sources you point it at (URLs, files, text you drop in). Curation is yours.
- **Not an agent framework.** brain has agent-like qualities (the 34 tools, the patch-proposal loop), but it's a purpose-built knowledge tool, not a general-purpose agent runtime. Use Claude Desktop + MCP for that pattern.

---

## Who it's for

You're probably a fit if:

- You already maintain notes — in Obsidian, in a git-versioned Markdown folder, in Apple Notes you wish was Markdown.
- You think about what you read. You write to think. You reread your own notes.
- You want AI help with synthesis + pushback + editing, without handing the keys to a third-party to do it.
- You work in a domain where your raw thinking is sensitive — competitive strategy, client work, research-in-progress, legal-adjacent analysis, journals.
- You care about "this still works in five years" more than "this is the newest thing."
- You have, or can get, an Anthropic API key, and you're comfortable running a local app. (No sudo, no admin, no dev tools required — but you will type in a terminal once.)

You're probably *not* a fit if:

- You want a cloud tool your team can share a URL to.
- You want something that runs on your phone primarily. (brain is desktop-first; mobile is roadmap.)
- You want cheap-and-infinite use. (LLM API costs scale with use. Budget caps are there for a reason.)
- You want something that works out of the box without *any* technical setup. (The install is one command, but it is a terminal command. The setup wizard is in the browser, but you have to start the app first.)

---

## Getting started

One command. No sudo, no admin.

**macOS 13+**

```bash
curl -fsSL https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/install.sh | bash
```

**Windows 11**

```powershell
irm https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/install.ps1 | iex
```

Then `brain start`. Your browser opens the setup wizard.

You'll need an [Anthropic API key](https://console.anthropic.com) — the wizard will ask for it. Everything else is defaults that you can change later via Settings.

- **Install time:** ~30 seconds on a warm network.
- **First chat turn:** ~3 seconds from browser to first streamed token.
- **Disk footprint:** ~500 MB for the app. Your vault grows with your notes.
- **Ongoing cost:** pay Anthropic (or configured provider) for the API tokens you use. Typical single-user use is in the range of a few dollars a month.

Uninstall is honest: `brain uninstall` asks four typed-confirmation questions. Your vault is preserved by default; typing `DELETE-VAULT` is the only way to remove your notes.

---

## What's next

v0.1.0 is the shippable first release. What's in motion:

- **Mobile-side read** — v0.2.0 adds a read-only iOS/Android view at `http://<your-mac>:4317/` so you can read notes from your phone.
- **Bulk migration** — bring a 5-year Obsidian vault or Notion export in one pass. Dry-run → review → apply.
- **Broken-wikilink detection** — visual flag on `[[links]]` that point nowhere yet.
- **Native PDF upload via the web UI** — today PDFs work through the CLI / MCP path; web upload is text-only for v0.1.0.
- **More LLM providers** — OpenAI, Google, local-only via Ollama. The `LLMProvider` abstraction was built for this.
- **Desktop wrapper** — a Tart / Tauri shell so double-clicking an app icon just works, no terminal needed.

The roadmap is public. The spec is public. The lessons from every prior release cycle are public. If you want to follow along, [watch the repo](https://github.com/ToTo-LLC/cj-llm-kb).

---

## A note on trust

You have no reason to trust a document that's trying to sell you on an LLM tool. Every word above could be a marketing lie. Here's what isn't:

- **The code is open source under MIT.** Read it. Grep it for `requests.post`. Count the outbound call sites. Run `tcpdump` while brain is running. The [privacy document](docs/privacy.md) makes specific, falsifiable claims.
- **The design document that led to the product is public.** See `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`. It's 2000+ lines written before a line of code landed. The architecture in this marketing document isn't a retrofit.
- **Every release has a public known-issues document.** See [`docs/v0.1.0-known-issues.md`](v0.1.0-known-issues.md). It lists what's broken, what's deferred, what ships with caveats. If a tool can't honestly tell you what it can't do yet, that's a tell.
- **The release notes admit the limits.** v0.1.0 ships with 5 known user-facing shortfalls documented in [the release notes](release-notes/v0.1.0.md) — no glossing.

If any of those claims turn out to be wrong, you have the receipts.

---

## One-line pitch, for when you need it

> brain turns a folder of Markdown files into an LLM-maintained wiki you own end-to-end — three chat modes (Ask / Brainstorm / Draft), staged changes with human approval, Obsidian-compatible vault, zero telemetry, Mac + Windows.

---

*brain is an open-source project by Chris Johnson ([@totollc](https://tomorrowtoday.com)). MIT licensed. v0.1.0 released 2026-04-24. Feedback, bug reports, and PRs welcome at [the issue tracker](https://github.com/ToTo-LLC/cj-llm-kb/issues).*
