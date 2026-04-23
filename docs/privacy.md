# Privacy

brain runs on your laptop. Your notes live in a folder you own. The only outbound calls brain makes are the ones you explicitly configure (LLM provider) plus an opt-out update check on `brain start` and the release-tarball download when you run `brain upgrade`. That's it.

This page spells out exactly what that means.

---

## What brain sends, and to whom

The only outbound network calls brain makes are:

1. **LLM API calls to your configured provider.** Anthropic is the day-one provider. Every prompt, tool call, ingest payload, and chat turn you send through brain goes to the provider you configured.
2. **An opt-out update check** on `brain start` (about one request, to `api.github.com`). Opt out with `BRAIN_NO_UPDATE_CHECK=1`.
3. **Tarball downloads** when you run `brain upgrade` — from the GitHub release asset URL for the version you're installing.

Nothing else. No analytics, no crash reporting, no "anonymized usage data," no phone-home. No outbound call happens on your behalf that isn't one of those three.

---

## What brain does NOT do

To remove all ambiguity, brain does not:

- Send **analytics** of any kind. No Mixpanel, Amplitude, PostHog, Segment, Google Analytics, or equivalent.
- Send **crash reports** or error beacons. No Sentry, Bugsnag, Rollbar, Datadog RUM, or equivalent.
- Connect to a **feature-flag service** (no LaunchDarkly, Statsig, etc.).
- Run **A/B tests** or experiments against you.
- Generate or transmit a **user ID**, device ID, install ID, or any stable identifier.
- Send a **heartbeat ping**, keepalive, or liveness beacon to any server.
- Record **referrers**, **UTM tags**, or install-source metadata.
- Report **install telemetry** — the installer does not ping home when it finishes.
- Collect **IP addresses** anywhere brain controls. (GitHub naturally logs the update-check and upgrade download per their standard terms; brain itself does not proxy those through a server it controls.)

If you find a network call that isn't covered by the three bullets above, that's a bug. Email chris@tomorrowtoday.com.

---

## Where your data lives

Everything brain knows about you lives on your own filesystem.

- **Vault** — your notes. Plain Markdown with YAML frontmatter.
  - **macOS:** `~/Documents/brain/`
  - **Windows:** `%USERPROFILE%\Documents\brain\`
  - You can move it anywhere readable during setup. It never leaves your disk unless you send a prompt that includes its contents to your LLM provider.

- **Secrets** — `.brain/secrets.env` inside the vault. Holds your LLM API key and the per-run local API token.
  - **macOS / Linux:** `chmod 0600` (owner read/write only).
  - **Windows (v0.1.0):** read-only filesystem bit. This is a known limitation tracked as [issue #5 in the v0.1.0 release notes](v0.1.0-known-issues.md) — full Windows ACL lockdown is planned for v0.2.0. The per-run API token still rotates on every `brain start`, and brain only binds to loopback, so a local account on your machine is the only way to read it.
  - Secrets are **never** written to logs.

- **SQLite caches** — `.brain/state.sqlite` and `.brain/costs.sqlite` inside the vault.
  - `state.sqlite` — the search and link index. Derived from vault content. Rebuildable at any time via `brain doctor --rebuild-cache`.
  - `costs.sqlite` — per-call LLM cost ledger (operation, model, tokens, cost, domain, timestamp).
  - Both are caches. The vault is the source of truth. Delete either and brain rebuilds it.

- **Logs** — `.brain/logs/brain-api.log` inside the vault. Rotated at 50MB. **LLM prompt and response bodies are not logged** unless you explicitly set `log_llm_payloads=true` in your config. Even with payloads enabled, logs never leave disk unless you send them somewhere.

Everything in `.brain/` (secrets, logs, run-state, caches) is ignored by default if you ever put the vault under version control. That's intentional.

---

## LLM API calls

When you send a message, brain ships the prompt plus any retrieved vault content to your configured LLM provider. For v0.1.0 that provider is **Anthropic**. The provider sees everything brain sends them for that call — the chat turn, any tool calls, any ingest payload, any document draft. brain itself doesn't see, log, or store those payloads beyond what the provider's SDK does in transit.

What the provider does with the data is governed by the provider's own privacy policy:

- **Anthropic:** <https://www.anthropic.com/privacy>

If you want stricter guarantees, Anthropic offers zero-retention arrangements for enterprise customers — configure that directly with them. brain doesn't override provider-side settings.

Cost metadata (tokens in / tokens out / dollars / operation name / domain) is logged locally in `costs.sqlite` so you can see what you spent. That ledger never leaves your machine.

---

## The update check

On `brain start`, brain fires a single HTTPS request:

```
GET https://api.github.com/repos/ToTo-LLC/cj-llm-kb/releases/latest
```

With a 3-second timeout. If there's a newer version than yours, brain prints a one-line nudge after the "running at ..." line. That's the entire interaction.

- brain adds **no identifying headers** and **no request body** beyond what the Python HTTP client adds by default (standard User-Agent, Accept headers). There is no install ID, no machine ID, no email, no hostname.
- GitHub's public API logs the request per their standard terms (including the source IP, as with any HTTPS request). brain does not proxy this through a server it controls.
- **Opt out:** set `BRAIN_NO_UPDATE_CHECK=1` in your environment. brain will skip the call entirely and print nothing.

`brain upgrade` makes a similar call plus downloads the release tarball from the GitHub release asset URL. Same opt-out.

---

## MCP / Claude Desktop integration

If you enabled Claude Desktop integration during setup, brain registers itself as an MCP server in Claude Desktop's config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows). Claude Desktop invokes the MCP server **locally via stdio** — no network hop between Claude Desktop and brain.

When Claude Desktop in turn makes LLM calls through MCP, those go to Anthropic per standard Claude Desktop behavior. brain doesn't intercept, log, or re-send those — they happen in Claude Desktop's process, not brain's. Anthropic's privacy policy covers what happens on the server side.

Uninstalling the MCP integration removes brain's entry from the Claude Desktop config. Your vault, API keys, and logs are untouched.

---

## Questions or reports

Anything in this document unclear, surprising, or contradicted by something you observe? Email **chris@tomorrowtoday.com**. Security-sensitive findings especially — please don't open a public issue for those; mail them to me and I'll coordinate a fix.
