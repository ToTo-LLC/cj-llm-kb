# Domain overrides and privacy rails

brain lets you tune two things per domain: which domains are excluded from default queries (the **privacy rail**), and which domains override the global LLM defaults (**domain overrides**). Both are edited from **Settings → Domains** in the web app.

## Privacy rails (`Config.privacy_railed`)

This is the list of domain slugs excluded from default and wildcard queries. Reading from a privacy-railed domain requires naming it explicitly in the `domains=` argument — it is never pulled in by a cross-domain or unscoped search.

The default is `["personal"]`. You can add any other domain (for example `medical` or `finance`). The `personal` slug is structurally required and cannot be removed.

## Domain overrides (`Config.domain_overrides`)

Each entry overrides the global LLM and autonomy settings for one domain. Available fields:

- `classify_model` — model used to classify content into this domain
- `default_model` — model used for chat and brainstorm
- `temperature` — sampling temperature
- `max_output_tokens` — output cap
- `autonomous_mode` — whether vault writes auto-approve

Any field left unset falls back to the global default.

## When changes take effect

Saved changes apply to **new** request handlers immediately. In-flight requests continue with the config they started with until they finish — invisible during normal UI use. To guarantee every active handler has the new config, restart the server with `brain restart`.
