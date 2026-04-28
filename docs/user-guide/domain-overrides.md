# Domain overrides and privacy rails

brain tunes two things per domain: which domains are excluded from default queries (the **privacy rail**), and which override the global LLM defaults (**domain overrides**). Edit both from **Settings → Domains**.

## Privacy rails (`Config.privacy_railed`)

This is the list of domain slugs excluded from default and wildcard queries. Reading from a privacy-railed domain requires naming it explicitly in the `domains=` argument — it is never pulled in by a cross-domain or unscoped search.

The default is `["personal"]`. You can add any other domain (for example `medical` or `finance`). The `personal` slug is structurally required and cannot be removed.

## Domain overrides (`Config.domain_overrides`)

Each entry overrides the global LLM and autonomy settings for one domain. Available fields:

- `classify_model` — model used to classify content into this domain
- `default_model` — model used for chat and brainstorm
- `temperature` — sampling temperature
- `max_output_tokens` — output cap
- `autonomous_mode` **(Plan 12+ — not yet wired)** — reserved for per-domain auto-approval of vault writes; setting this today has no effect.

Any field left unset falls back to the global default.

## When changes take effect

Saved changes are visible to the same process immediately — the next call to a tool that reads `Config` sees the new value, even mid-handler. No restart needed for changes made by your own session.

Other processes (the MCP server `brain_mcp`, a separate `brain` CLI invocation) hold their own cached `Config` and pick up changes only on next start. To guarantee every process is using the new config, run `brain restart`.
