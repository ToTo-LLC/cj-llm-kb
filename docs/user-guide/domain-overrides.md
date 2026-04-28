# Domain overrides and privacy rails

brain tunes two things per domain: which domains are excluded from default queries (the **privacy rail**), and which override the global LLM defaults (**domain overrides**). Edit both from **Settings → Domains**.

## Privacy rails (`Config.privacy_railed`)

This is the list of domain slugs excluded from default and wildcard queries. Reading from a privacy-railed domain requires naming it explicitly in the `domains=` argument — it is never pulled in by a cross-domain or unscoped search.

The default is `["personal"]`. You can add any other domain (for example `medical` or `finance`). The `personal` slug is structurally required and cannot be removed.

## Domain overrides (`Config.domain_overrides`)

Each entry overrides the global LLM settings for one domain. Available fields:

- `classify_model` — model used to classify content into this domain
- `default_model` — model used for chat and brainstorm
- `temperature` — sampling temperature
- `max_output_tokens` — output cap

Any field left unset falls back to the global default.

## Cross-domain confirmation modal

When you start a new chat / brainstorm / draft session whose scope spans **two or more domains** AND **at least one of them is in `Config.privacy_railed`**, brain shows a one-time confirmation modal before the first send. The modal lists the railed slugs in the scope so you can confirm or back out before any privacy-railed content flows into a multi-domain conversation.

**Why this matters.** Privacy-railed domains (default: `personal`) are structurally excluded from default and wildcard queries — naming them explicitly in a multi-domain scope is the only way they enter the conversation. The modal is the second checkpoint: it surfaces the explicit inclusion so you don't accidentally cross-pollinate `research` and `personal` in a brainstorm session you meant to scope to `research` alone. Single-domain railed scopes (`scope=[personal]` only) do not fire the modal — the explicit slug inclusion is itself the consent. Pure cross-domain scopes without any railed slug (e.g. `scope=[research, work]`) also do not fire — there is no privacy rail to cross.

**Dismissing permanently.** The modal includes a "Don't show this again" checkbox. Checking it before clicking **Continue** persists `Config.cross_domain_warning_acknowledged = true` to `<vault>/.brain/config.json`, suppressing the modal for every future cross-domain-with-rail scope on this vault.

**Re-enabling.** Settings → Domains has a **"Show cross-domain warning"** toggle. Switching it on resets `Config.cross_domain_warning_acknowledged` to `false`, so the next cross-domain-with-rail scope will surface the modal again. Use this if you dismissed it by accident, want a refresher before a sensitive session, or are setting up brain for a new household member who hasn't seen the warning yet.

## When changes take effect

Saved changes are visible to the same process immediately — the next call to a tool that reads `Config` sees the new value, even mid-handler. No restart needed for changes made by your own session.

Other processes (the MCP server `brain_mcp`, a separate `brain` CLI invocation) hold their own cached `Config` and pick up changes only on next start. To guarantee every process is using the new config, run `brain restart`.
