// Typed bindings for every registered brain tool.
//
// One named export per tool. Arguments mirror each tool's ``INPUT_SCHEMA``
// (see ``packages/brain_core/src/brain_core/tools/*.py``). Data shapes
// approximate each handler's ``ToolResult.data`` — heterogeneous / rich
// payloads stay as ``Record<string, unknown>`` so individual tool bindings
// don't over-constrain callers that want to treat the payload opaquely.
//
// Plan 07 Task 9 / Task 16 / Task 20 / Task 25B: 34 tools total. 18 from
// Plan 04 (read / ingest / patch / maintenance) + 4 added in Plan 07 Task 4
// (recent_ingests, create_domain, rename_domain, budget_override) + 1 added
// in Plan 07 Task 16 (get_pending_patch — envelope + body for the approval
// detail pane) + 1 added in Plan 07 Task 20 (fork_thread — Fork dialog) +
// 10 added in Plan 07 Task 25A/B (mcp install/uninstall/status/selftest,
// set_api_key, ping_llm, backup_create/list/restore, delete_domain).
//
// Every binding ultimately calls ``POST /api/tools/<name>`` via the proxy.

import { apiFetch } from "./client";
import type { ToolResponse } from "./types";

// ---------- helpers ----------

function callTool<D = Record<string, unknown>>(
  name: string,
  args: Record<string, unknown> = {},
): Promise<ToolResponse<D>> {
  return apiFetch<D>(`/api/tools/${name}`, {
    method: "POST",
    body: JSON.stringify(args),
  });
}

// ---------- shared shapes ----------

export interface SearchHit {
  path: string;
  title: string;
  snippet: string;
  score: number;
}

/**
 * One row from the ``brain_recent`` handler.
 *
 * Mirrors the backend row shape post-Plan-17 T16 — only ``path`` and
 * ``modified_at`` are emitted (see
 * ``packages/brain_core/src/brain_core/tools/recent.py``). Callers that
 * need a richer display shape (title / domain / etc.) reconstruct it
 * locally from the path; see ``browse-screen.tsx`` for the canonical
 * example (``slugOf`` + ``domainOf`` helpers). Plan 18 T1 narrowed this
 * type from a wider drifted shape that had silently masked a runtime
 * ``TypeError`` in the doc-picker scope/search filters.
 */
export interface RecentEntry {
  path: string;
  modified_at: string; // ISO-8601 timestamp
}

export interface PendingPatch {
  patch_id: string;
  target_path: string;
  reason: string;
  created_at: string; // ISO-8601 timestamp
  [extra: string]: unknown; // envelope may carry extra tool-specific fields
}

/**
 * Mirrors a row in `brain_recent_ingests`'s `ToolResult.data.ingests`
 * (see `packages/brain_core/src/brain_core/tools/recent_ingests.py`).
 * Backend is source of truth; the Plan 18 T3.1 alignment narrowed `at`
 * → `classified_at` and `items` → `ingests` (outer-shape rename below)
 * and added explicit optional fields for the backend's other emitted
 * keys (`source_type`, `cost_usd`, `patch_id`, `error`) so type-aware
 * callers can read them without `as`-casts.
 */
export interface RecentIngestEntry {
  source: string;
  source_type: string; // backend always emits (column from ingest_history)
  domain: string | null;
  status: string;
  classified_at: string; // ISO-8601 timestamp
  cost_usd: number; // backend always emits (defaults to 0.0)
  patch_id?: string; // backend conditionally emits (only when non-null)
  error?: string; // backend conditionally emits (only when non-null)
  [extra: string]: unknown; // keep escape hatch for future fields
}

// ---------- read tools (6) ----------

/**
 * Return every domain slug the caller is allowed to read.
 *
 * Plan 10 Task 5 added the per-slug ``entries`` array (configured / on_disk
 * flags). Plan 11 Task 6 added ``active_domain`` so the frontend can
 * hydrate the topbar scope picker on first mount (Task 8). Older
 * back-ends that pre-date Task 6 simply omit ``active_domain`` — callers
 * must guard for ``undefined``.
 */
export const listDomains = (): Promise<
  ToolResponse<{
    domains: string[];
    entries?: Array<{ slug: string; configured: boolean; on_disk: boolean }>;
    active_domain?: string;
  }>
> =>
  callTool<{
    domains: string[];
    entries?: Array<{ slug: string; configured: boolean; on_disk: boolean }>;
    active_domain?: string;
  }>("brain_list_domains");

/**
 * Read `<domain>/index.md`. `domain` defaults to the first allowed domain.
 *
 * Mirrors the `brain_get_index` backend handler (see
 * `packages/brain_core/src/brain_core/tools/get_index.py`); both the
 * happy path and the missing-file branch emit `{domain, frontmatter, body}`.
 * Plan 18 T3.2 narrowed the TS interface from `{path, content}` (which
 * never matched backend) to the real shape. No active consumer at the
 * time of the narrow.
 */
export const getIndex = (
  args: { domain?: string } = {},
): Promise<
  ToolResponse<{
    domain: string;
    frontmatter: Record<string, unknown>;
    body: string;
  }>
> =>
  callTool<{
    domain: string;
    frontmatter: Record<string, unknown>;
    body: string;
  }>("brain_get_index", args);

/** Read a note by vault-relative path. */
export const readNote = (
  args: { path: string },
): Promise<
  ToolResponse<{
    path: string;
    frontmatter: Record<string, unknown>;
    body: string;
  }>
> =>
  callTool<{
    path: string;
    frontmatter: Record<string, unknown>;
    body: string;
  }>("brain_read_note", args);

/** BM25 search across allowed domains. */
export const search = (
  args: { query: string; top_k?: number; domains?: string[] },
): Promise<ToolResponse<{ hits: SearchHit[]; top_k_used: number }>> =>
  callTool<{ hits: SearchHit[]; top_k_used: number }>("brain_search", args);

/** List recently modified notes. */
export const recent = (
  args: { domain?: string; limit?: number } = {},
): Promise<ToolResponse<{ items: RecentEntry[] }>> =>
  callTool<{ items: RecentEntry[] }>("brain_recent", args);

/** Issue #18: list recent chat threads in scope. The state.sqlite
 *  ``chat_threads`` table is the source of truth — populated by the chat
 *  persistence layer on every turn write. */
export interface ChatThreadEntry {
  thread_id: string;
  path: string;
  domain: string;
  mode: string;
  turns: number;
  cost_usd: number;
  updated_at: string;
}

export const listThreads = (
  args: { domain?: string; query?: string; limit?: number } = {},
): Promise<ToolResponse<{ threads: ChatThreadEntry[] }>> =>
  callTool<{ threads: ChatThreadEntry[] }>("brain_list_threads", args);

/** Issue #17: read a thread file from the vault and return its markdown
 *  content. The frontend turns ``data.markdown`` into a downloadable
 *  ``.md`` file via a data URL. */
export const exportThread = (
  args: { thread_id: string },
): Promise<
  ToolResponse<{
    thread_id: string;
    path: string;
    domain: string;
    markdown: string;
    filename: string;
    byte_length: number;
  }>
> =>
  callTool<{
    thread_id: string;
    path: string;
    domain: string;
    markdown: string;
    filename: string;
    byte_length: number;
  }>("brain_export_thread", args);

/**
 * Fetch the top-level `BRAIN.md` meta-index.
 *
 * Mirrors the `brain_get_brain_md` backend handler (see
 * `packages/brain_core/src/brain_core/tools/get_brain_md.py`); both
 * the happy path and the missing-file branch emit `{exists, body}`.
 * Plan 18 T3.3 narrowed the TS interface from `{path, content}`
 * (which never matched backend) to the real shape. No active consumer
 * at the time of the narrow.
 */
export const getBrainMd = (): Promise<
  ToolResponse<{ exists: boolean; body: string }>
> =>
  callTool<{ exists: boolean; body: string }>("brain_get_brain_md");

// ---------- ingest tools (3) ----------

/** Ingest a URL, file path, or raw text. Default stages a patch. */
export const ingest = (args: {
  source: string;
  autonomous?: boolean;
  domain_override?: string;
}): Promise<
  ToolResponse<{
    patch_id: string | null;
    applied: boolean;
    domain: string | null;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    patch_id: string | null;
    applied: boolean;
    domain: string | null;
    [extra: string]: unknown;
  }>("brain_ingest", args);

/** Classify a piece of content. Returns a domain + confidence score. */
export const classify = (args: {
  content: string;
  hint?: string;
}): Promise<
  ToolResponse<{
    domain: string;
    confidence: number;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    domain: string;
    confidence: number;
    [extra: string]: unknown;
  }>("brain_classify", args);

/** Bulk-import a folder. ``dry_run`` defaults to true. */
export const bulkImport = (args: {
  folder: string;
  dry_run?: boolean;
  max_files?: number;
}): Promise<
  ToolResponse<{
    plan: Array<Record<string, unknown>>;
    applied: boolean;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    plan: Array<Record<string, unknown>>;
    applied: boolean;
    [extra: string]: unknown;
  }>("brain_bulk_import", args);

// ---------- write / patch tools (5) ----------

/** Stage a new note for approval. */
export const proposeNote = (args: {
  path: string;
  content: string;
  reason: string;
}): Promise<ToolResponse<{ patch_id: string; target_path: string }>> =>
  callTool<{ patch_id: string; target_path: string }>(
    "brain_propose_note",
    args,
  );

/** List pending patches in the approval queue. */
export const listPendingPatches = (
  args: { limit?: number } = {},
): Promise<ToolResponse<{ patches: PendingPatch[] }>> =>
  callTool<{ patches: PendingPatch[] }>("brain_list_pending_patches", args);

/**
 * Fetch one pending patch by id — envelope metadata PLUS the full patchset
 * body (``new_files`` / ``edits`` / ``index_entries`` / ``log_entry``).
 * Used by the Plan 07 Task 16 pending-approval detail pane, which needs the
 * body to render a diff. ``listPendingPatches`` deliberately omits the body
 * for that reason; this is the complementary by-id read.
 */
export const getPendingPatch = (args: {
  patch_id: string;
}): Promise<
  ToolResponse<{
    envelope: Record<string, unknown>;
    patchset: Record<string, unknown>;
  }>
> =>
  callTool<{
    envelope: Record<string, unknown>;
    patchset: Record<string, unknown>;
  }>("brain_get_pending_patch", args);

/** Apply a staged patch. */
export const applyPatch = (args: {
  patch_id: string;
}): Promise<
  ToolResponse<{
    patch_id: string;
    undo_id: string;
    applied_files: string[];
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    patch_id: string;
    undo_id: string;
    applied_files: string[];
    [extra: string]: unknown;
  }>("brain_apply_patch", args);

/** Reject a staged patch with a human-readable reason. */
export const rejectPatch = (args: {
  patch_id: string;
  reason: string;
}): Promise<ToolResponse<{ patch_id: string; rejected: boolean }>> =>
  callTool<{ patch_id: string; rejected: boolean }>("brain_reject_patch", args);

/** Revert the most recent applied write (or a specific ``undo_id``). */
export const undoLast = (
  args: { undo_id?: string } = {},
): Promise<
  ToolResponse<{
    undo_id: string;
    reverted_files: string[];
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    undo_id: string;
    reverted_files: string[];
    [extra: string]: unknown;
  }>("brain_undo_last", args);

// ---------- maintenance tools (4) ----------

/** Summarise spend-to-date. Cumulative USD + per-operation break-down. */
export const costReport = (): Promise<
  ToolResponse<{
    total_usd: number;
    by_operation: Record<string, number>;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    total_usd: number;
    by_operation: Record<string, number>;
    [extra: string]: unknown;
  }>("brain_cost_report");

/**
 * Run lint checks across a domain (or every allowed domain if omitted).
 *
 * **Stub until Plan 09 lands the real lint engine.** The backend handler
 * (`packages/brain_core/src/brain_core/tools/lint.py`) currently always
 * returns `{status: "not_implemented", message: "..."}` — Plan 18 T3.4
 * narrowed this TS interface to match the stub reality. When Plan 09
 * delivers wikilink checking, orphan detection, and frontmatter
 * validation, the backend `data` shape will change to include
 * `findings: Array<...>`, at which point this TS interface needs to be
 * widened to a discriminated union (e.g.,
 * `{status: "not_implemented", message: string} | {findings: ...}`) or
 * replaced outright. The Python key-set pin in `test_lint.py` will fail
 * RED when Plan 09 changes the backend, surfacing the need to update.
 */
export const lint = (
  args: { domain?: string } = {},
): Promise<ToolResponse<{ status: string; message: string }>> =>
  callTool<{ status: string; message: string }>("brain_lint", args);

/** Read a single config key. */
export const configGet = (args: {
  key: string;
}): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  callTool<{ key: string; value: unknown }>("brain_config_get", args);

// ---------- Plan 16 Task 33 — Repair-config dialog ----------

/**
 * One row in the per-step results panel (Plan 16 Task 33). Mirrors the
 * Python ``brain_core.tools.repair_config.handle`` step shape:
 *
 *   - ``step``    — canonical step id (``read_primary``, ``validate_primary``,
 *                   ``read_backup``, ``validate_backup``, ``apply_defaults``)
 *   - ``status``  — ``"success"`` | ``"warning"`` | ``"error"``
 *   - ``message`` — human-readable one-liner; for errors carries the
 *                   underlying error text.
 *
 * Steps that did NOT run (because earlier steps already succeeded) are
 * NOT in the returned array — keeps the UI compact.
 */
export interface RepairConfigStep {
  step:
    | "read_primary"
    | "validate_primary"
    | "read_backup"
    | "validate_backup"
    | "apply_defaults";
  status: "success" | "warning" | "error";
  message: string;
}

/**
 * Full payload returned by ``brain_repair_config``. The
 * ``repaired_config`` blob is the persisted-dict shape that the Re-apply
 * action posts back to ``brain_repair_config_apply`` to commit the
 * recovered Config to disk.
 */
export interface RepairConfigData {
  steps: RepairConfigStep[];
  repair_changes_pending: boolean;
  repaired_config: Record<string, unknown>;
}

/**
 * Re-run the config-load fallback chain (Plan 16 Task 33). Read-only; the
 * Re-apply button calls :func:`repairConfigApply` with the
 * ``repaired_config`` payload returned here. The split mirrors
 * ``brain_backup_create`` / ``brain_backup_restore`` (Option 1: two
 * tools, two responsibilities — see backend dispatch text).
 */
export const repairConfig = (): Promise<ToolResponse<RepairConfigData>> =>
  callTool<RepairConfigData>("brain_repair_config");

/**
 * Apply a repaired config payload to disk (Plan 16 Task 33). The
 * payload comes from a prior :func:`repairConfig` call's
 * ``data.repaired_config`` — the frontend round-trips it back to the
 * backend rather than re-deriving the recovered state. Returns
 * ``{status:"applied", path, config_version}`` on success; throws
 * :class:`ApiError` on schema validation failure or disk-write failure.
 */
export const repairConfigApply = (
  repaired: Record<string, unknown>,
): Promise<
  ToolResponse<{ status: string; path: string; config_version: number }>
> =>
  callTool<{ status: string; path: string; config_version: number }>(
    "brain_repair_config_apply",
    { repaired_config: repaired },
  );

/** Write a single config key. ``value`` is validated server-side. */
export const configSet = (args: {
  key: string;
  value: unknown;
}): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  callTool<{ key: string; value: unknown }>("brain_config_set", args);

// ---------- Plan 11 Task 7 — domain overrides + privacy-rail helpers ----------

/** Field names settable on ``DomainOverride`` (Plan 11 D12). */
export type DomainOverrideField =
  | "classify_model"
  | "default_model"
  | "temperature"
  | "max_output_tokens"
  | "autonomous_mode";

/**
 * Set a single per-domain override field (or clear it with ``null``).
 * Routes through ``brain_config_set`` with the dotted key
 * ``domain_overrides.<slug>.<field>``; the backend's dict-walk
 * extension (Plan 11 Task 7) handles the open-set ``<slug>`` segment
 * and auto-creates the per-slug ``DomainOverride`` entry on first set.
 *
 * Passing ``null`` clears the override for that field (Reset to
 * global). When the last field on a slug is cleared, the slug entry
 * is pruned from ``Config.domain_overrides`` server-side.
 */
export const setDomainOverride = (args: {
  slug: string;
  field: DomainOverrideField;
  value: string | number | boolean | null;
}): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({
    key: `domain_overrides.${args.slug}.${args.field}`,
    value: args.value,
  });

/**
 * Replace the privacy-rail slug list. ``personal`` is required (the
 * Config validator enforces it on persist) — callers should never send
 * a list missing ``personal``. Mutations are whole-list — the caller
 * computes the new list (existing + added slug, or existing minus
 * removed slug) and posts it here.
 */
export const setPrivacyRailed = (
  list: string[],
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({ key: "privacy_railed", value: list });

/**
 * Per-domain budget cap payload — mirrors
 * :class:`brain_core.config.schema.BudgetOverride`. Either / both caps may
 * be omitted or set to ``null`` (= "no override; fall back to global"); a
 * positive numeric overrides the global :class:`BudgetConfig` cap for
 * spend attributed to this domain. Zero / negative caps are rejected at
 * the schema level — the documented way to clear a cap is ``null`` (or
 * omitting the field).
 */
export interface BudgetCap {
  monthly_cap_usd?: number | null;
  daily_cap_usd?: number | null;
}

/**
 * Persist a per-domain budget cap entry (Plan 16 Task 29 / D26 step 4 of 4).
 * Routes through ``brain_config_set`` with the dotted key
 * ``budget.per_domain.<slug>`` — the backend's wildcard handler
 * (``_apply_budget_per_domain``) writes the whole BudgetOverride payload
 * at once. Posting ``null`` for the value drops the slug entry entirely
 * (equivalent to "no override; fall back to the global
 * :class:`BudgetConfig` caps"); posting a payload where both caps are
 * ``null`` is also pruned to "no entry" by the backend.
 *
 * Unlike ``setDomainOverride`` (which writes one leaf field at a time),
 * the budget cap path is whole-payload because the Settings UI sets
 * daily / monthly as a pair and a half-applied save would leave
 * inconsistent state on disk if one leaf write failed.
 */
export const setDomainBudget = (
  slug: string,
  cap: BudgetCap | null,
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({
    key: `budget.per_domain.${slug}`,
    value: cap,
  });

/**
 * Per-domain rate-limit override payload — mirrors
 * :class:`brain_core.config.schema.RateLimitOverride`. ``requests_per_minute``
 * may be omitted or set to ``null`` (= "no override; the provider bypasses
 * rate-limit gating for this domain"); a positive integer caps the per-minute
 * request rate for spend attributed to this domain. Zero / negative values
 * are rejected at the schema level — the documented way to clear an
 * override is ``null`` (or omitting the field).
 */
export interface RateLimitOverride {
  requests_per_minute?: number | null;
}

/**
 * Persist a per-domain rate-limit entry (Plan 16 Task 32 / D27 step 3 of 3).
 * Routes through ``brain_config_set`` with the dotted key
 * ``providers.anthropic.rate_limit_per_domain.<slug>`` — the backend's
 * wildcard handler (``_apply_rate_limit_per_domain``) writes the whole
 * RateLimitOverride payload at once, auto-creating the parent
 * ``ProviderConfig`` on first set. Posting ``null`` for the value drops the
 * slug entry entirely (equivalent to "no override; provider bypasses
 * rate-limit gating for this domain"); posting a payload where
 * ``requests_per_minute`` is ``null`` is also pruned to "no entry" by the
 * backend.
 *
 * The ``provider`` argument defaults to ``"anthropic"`` because that's
 * the only LLM provider implementation today; the wire shape supports
 * additional providers without a frontend change.
 *
 * Whole-payload semantics mirror :func:`setDomainBudget` — even though
 * RateLimitOverride only has one leaf field today, the contract
 * future-proofs the wire shape if the override grows additional fields.
 */
export const setDomainRateLimit = (
  slug: string,
  override: RateLimitOverride | null,
  provider: string = "anthropic",
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({
    key: `providers.${provider}.rate_limit_per_domain.${slug}`,
    value: override,
  });

/**
 * Per-domain × per-category autonomy flag categories (Plan 16 Task 40 /
 * D30 step 4 of 4). HYBRID surface (T37 §1): three are
 * :class:`brain_core.vault.types.PatchSet` member-field names
 * (``new_files``, ``edits``, ``index_entries``); two are
 * :class:`brain_core.vault.types.PatchCategory` values (``concepts``,
 * ``draft``). Mirrors the Python schema's
 * :class:`brain_core.config.schema.AutonomyCategoryFlags` field set
 * exactly — drift would silently make a new flag non-settable from the
 * Settings UI.
 */
export type AutonomyCategory =
  | "new_files"
  | "edits"
  | "index_entries"
  | "concepts"
  | "draft";

/** Iteration-friendly readonly tuple of every autonomy category in the
 *  canonical UI order (matches ``Config.autonomous`` row layout). */
export const AUTONOMY_CATEGORIES = [
  "new_files",
  "edits",
  "index_entries",
  "concepts",
  "draft",
] as const satisfies readonly AutonomyCategory[];

/**
 * Persist a single per-domain × per-category autonomy flag (Plan 16
 * Task 40 / D30 step 4 of 4). Routes through ``brain_config_set`` with
 * the dotted key ``autonomous.<slug>.<category>`` — the backend's
 * wildcard handler (``_apply_autonomous_per_domain``) auto-creates the
 * per-slug :class:`AutonomyCategoryFlags` entry on first set; mutates
 * the existing entry's leaf field via ``setattr`` on subsequent sets.
 *
 * Per-leaf semantics (unlike :func:`setDomainBudget` which writes a
 * whole :class:`BudgetOverride` payload at once) — every Switch in the
 * Settings → Autonomy grid toggles independently, so a single-leaf
 * write is the natural shape.
 *
 * Setting every flag in the entry to ``false`` causes the backend to
 * prune the slug entry entirely (the gate treats a missing slug the
 * same as an explicit all-False entry; CLAUDE.md principle #3 keeps
 * out-of-the-box every flag off).
 */
export const setDomainAutonomy = (
  slug: string,
  category: AutonomyCategory,
  value: boolean,
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({
    key: `autonomous.${slug}.${category}`,
    value,
  });

/**
 * Persist a new ``active_domain`` slug (Plan 12 D2 / Task 6).
 *
 * Self-documenting wrapper around ``configSet({key:"active_domain",
 * value: slug})`` — the inline call works too but is less clear at
 * the Settings UI consumer site (Plan 12 Task 8). The backend's
 * cross-field pre-check enforces "must be in ``Config.domains``" and
 * raises a structured validation error otherwise; Settings UI awaits
 * + toasts on error per Plan 12 Task 8.
 */
export const setActiveDomain = (
  slug: string,
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({ key: "active_domain", value: slug });

/**
 * Persist the cross-domain confirmation acknowledgment flag (Plan 12 D8 /
 * Task 9). ``true`` suppresses the modal in future sessions; ``false``
 * re-enables it.
 *
 * Self-documenting wrapper around ``configSet({key:
 * "cross_domain_warning_acknowledged", value})`` — mirrors the
 * ``setActiveDomain`` shape so cross-domain modal call sites and the
 * Settings toggle share one helper. The Config field is whitelisted in
 * ``_SETTABLE_KEYS`` (Plan 12 Task 1 added the schema field; the key
 * is settable because it's a top-level Config bool — same path as
 * ``classify_model``, ``default_model``, etc.).
 */
export const setCrossDomainWarningAcknowledged = (
  value: boolean,
): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  configSet({ key: "cross_domain_warning_acknowledged", value });

// ---------- Plan 07 Task 4 additions (4) ----------

/**
 * List recent ingest runs. Mirrors the `brain_recent_ingests` backend
 * shape: `{ingests: RecentIngestEntry[]}`.
 *
 * Plan 18 T3.1: outer key narrowed from `items` to `ingests` to match
 * the backend handler (see `recent_ingests.py:48-90`). The doc-picker
 * sibling T1 fix used the same backend-is-source-of-truth direction.
 */
export const recentIngests = (
  args: { limit?: number } = {},
): Promise<ToolResponse<{ ingests: RecentIngestEntry[] }>> =>
  callTool<{ ingests: RecentIngestEntry[] }>("brain_recent_ingests", args);

/** Create a new domain with a slug, display name, and accent colour. */
export const createDomain = (args: {
  slug: string;
  name: string;
  accent_color?: string;
}): Promise<
  ToolResponse<{
    slug: string;
    name: string;
    accent_color: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    slug: string;
    name: string;
    accent_color: string;
    [extra: string]: unknown;
  }>("brain_create_domain", args);

/** Rename a domain slug. Optionally rewrites frontmatter ``domain:`` tags. */
export const renameDomain = (args: {
  from: string;
  to: string;
  rewrite_frontmatter?: boolean;
}): Promise<
  ToolResponse<{
    from: string;
    to: string;
    files_updated: number;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    from: string;
    to: string;
    files_updated: number;
    [extra: string]: unknown;
  }>("brain_rename_domain", args);

/** Temporarily bump the cost-budget ceiling. */
export const budgetOverride = (args: {
  amount_usd: number;
  duration_hours?: number;
}): Promise<
  ToolResponse<{
    amount_usd: number;
    duration_hours: number;
    expires_at: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    amount_usd: number;
    duration_hours: number;
    expires_at: string;
    [extra: string]: unknown;
  }>("brain_budget_override", args);

// ---------- Plan 07 Task 20 addition (1) ----------

/**
 * Fork a chat thread at a given turn index into a new thread. Returns the
 * newly-minted ``new_thread_id`` so the Fork dialog can navigate to it.
 * Carry modes: ``full`` (copy turns verbatim), ``none`` (empty),
 * ``summary`` (Haiku-cheap prose summary as one SYSTEM entry).
 */
export const forkThread = (args: {
  source_thread_id: string;
  turn_index: number;
  carry: "full" | "none" | "summary";
  mode: "ask" | "brainstorm" | "draft";
  title_hint?: string | null;
}): Promise<ToolResponse<{ new_thread_id: string }>> =>
  callTool<{ new_thread_id: string }>("brain_fork_thread", args);

// ---------- Plan 07 Task 25A/B additions (10) ----------

// --- Claude Desktop / MCP (4) ---

/**
 * Install the brain MCP entry into Claude Desktop's config. ``command`` is
 * required; ``args`` / ``env`` / ``server_name`` / ``config_path`` are all
 * optional. Writes a timestamped backup of any prior config before mutating.
 */
export const brainMcpInstall = (args: {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  config_path?: string;
  server_name?: string;
}): Promise<
  ToolResponse<{
    status: string;
    config_path: string;
    backup_path: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    config_path: string;
    backup_path: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>("brain_mcp_install", args);

/**
 * Remove the brain MCP entry from Claude Desktop's config. No-op when
 * absent. Always writes a timestamped backup before mutating.
 */
export const brainMcpUninstall = (
  args: { config_path?: string; server_name?: string } = {},
): Promise<
  ToolResponse<{
    status: string;
    config_path: string;
    backup_path?: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    config_path: string;
    backup_path?: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>("brain_mcp_uninstall", args);

/**
 * Report current Claude Desktop integration status (config path, entry
 * presence, executable resolution). Read-only.
 */
export const brainMcpStatus = (
  args: { config_path?: string; server_name?: string } = {},
): Promise<
  ToolResponse<{
    status: string;
    config_path: string;
    config_exists: boolean;
    entry_present: boolean;
    executable_resolves: boolean;
    command: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    config_path: string;
    config_exists: boolean;
    entry_present: boolean;
    executable_resolves: boolean;
    command: string | null;
    server_name: string;
    [extra: string]: unknown;
  }>("brain_mcp_status", args);

/**
 * File-layer self-test of the Claude Desktop integration (config exists,
 * entry present, command executable resolves). Does NOT spawn the MCP
 * server — full subprocess round-trip lives in the CLI.
 */
export const brainMcpSelftest = (
  args: { config_path?: string; server_name?: string } = {},
): Promise<
  ToolResponse<{
    status: string;
    ok: boolean;
    config_exists: boolean;
    entry_present: boolean;
    executable_resolves: boolean;
    command: string | null;
    config_path: string;
    server_name: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    ok: boolean;
    config_exists: boolean;
    entry_present: boolean;
    executable_resolves: boolean;
    command: string | null;
    config_path: string;
    server_name: string;
    [extra: string]: unknown;
  }>("brain_mcp_selftest", args);

// --- Provider key + health (2) ---

/**
 * Save an LLM provider API key to ``<vault>/.brain/secrets.env`` (0600 on
 * POSIX). The plaintext key is NEVER echoed back — the response returns
 * a masked suffix only.
 */
export const brainSetApiKey = (args: {
  provider: "anthropic";
  api_key: string;
}): Promise<
  ToolResponse<{
    status: string;
    provider: string;
    env_key: string;
    masked: string;
    path: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    provider: string;
    env_key: string;
    masked: string;
    path: string;
    [extra: string]: unknown;
  }>("brain_set_api_key", args);

/**
 * Send a 1-token probe to the configured LLM provider. Returns
 * ``{ok, latency_ms, provider, model}``, or ``ok=false`` with ``error``
 * on failure (failures are returned in the envelope, not thrown, so the
 * UI has a stable shape to render).
 */
export const brainPingLlm = (
  args: { model?: string } = {},
): Promise<
  ToolResponse<{
    ok: boolean;
    provider: string | null;
    model: string | null;
    latency_ms: number;
    error?: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    ok: boolean;
    provider: string | null;
    model: string | null;
    latency_ms: number;
    error?: string;
    [extra: string]: unknown;
  }>("brain_ping_llm", args);

// --- Backups (3) ---

export interface BackupEntry {
  backup_id: string;
  path: string;
  trigger: string;
  created_at: string; // ISO-8601
  size_bytes: number;
  file_count: number;
  [extra: string]: unknown;
}

/** Create a gzip-tarball snapshot of the vault. */
export const brainBackupCreate = (
  args: { trigger?: "manual" | "daily" | "pre_bulk_import" } = {},
): Promise<
  ToolResponse<{
    status: string;
    backup_id: string;
    path: string;
    trigger: string;
    created_at: string;
    size_bytes: number;
    file_count: number;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    backup_id: string;
    path: string;
    trigger: string;
    created_at: string;
    size_bytes: number;
    file_count: number;
    [extra: string]: unknown;
  }>("brain_backup_create", args);

/** List existing vault snapshots, newest first. */
export const brainBackupList = (): Promise<
  ToolResponse<{ backups: BackupEntry[] }>
> => callTool<{ backups: BackupEntry[] }>("brain_backup_list");

/**
 * Restore a vault snapshot over the current vault. Requires
 * ``typed_confirm=true``. Previous vault contents are moved to a
 * timestamped trash directory rather than deleted.
 */
export const brainBackupRestore = (args: {
  backup_id: string;
  typed_confirm: boolean;
}): Promise<
  ToolResponse<{
    status: string;
    backup_id: string;
    trash_path: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    backup_id: string;
    trash_path: string;
    [extra: string]: unknown;
  }>("brain_backup_restore", args);

// --- Domains (1) ---

/**
 * Move a vault domain to ``<vault>/.brain/trash/`` (reversible via
 * ``brain_undo_last``). Requires ``typed_confirm=true``. Refuses the
 * reserved ``personal`` slug unconditionally.
 */
export const brainDeleteDomain = (args: {
  slug: string;
  typed_confirm: boolean;
}): Promise<
  ToolResponse<{
    status: string;
    slug: string;
    trash_path: string;
    files_moved: number;
    undo_id: string;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    status: string;
    slug: string;
    trash_path: string;
    files_moved: number;
    undo_id: string;
    [extra: string]: unknown;
  }>("brain_delete_domain", args);

// ---------- registry ----------

/**
 * Machine-readable list of every bound tool. Kept in sync manually with
 * the exports above. Used by the Task 9 test suite to assert all 34
 * tools have typed bindings; a stale entry here means the client missed
 * a registry addition.
 */
export const ALL_TOOL_NAMES = [
  // read (6)
  "brain_list_domains",
  "brain_get_index",
  "brain_read_note",
  "brain_search",
  "brain_recent",
  "brain_get_brain_md",
  // ingest (3)
  "brain_ingest",
  "brain_classify",
  "brain_bulk_import",
  // write / patch (6)
  "brain_propose_note",
  "brain_list_pending_patches",
  "brain_get_pending_patch",
  "brain_apply_patch",
  "brain_reject_patch",
  "brain_undo_last",
  // maintenance (4)
  "brain_cost_report",
  "brain_lint",
  "brain_config_get",
  "brain_config_set",
  // Plan 07 Task 4 (4)
  "brain_recent_ingests",
  "brain_create_domain",
  "brain_rename_domain",
  "brain_budget_override",
  // Plan 07 Task 20 (1)
  "brain_fork_thread",
  // Plan 07 Task 25A/B (10)
  "brain_mcp_install",
  "brain_mcp_uninstall",
  "brain_mcp_status",
  "brain_mcp_selftest",
  "brain_set_api_key",
  "brain_ping_llm",
  "brain_backup_create",
  "brain_backup_list",
  "brain_backup_restore",
  "brain_delete_domain",
  // Issue #18 — left-nav recent-chats data source.
  "brain_list_threads",
  // Issue #17 — chat-sub-header export-thread action.
  "brain_export_thread",
  // Plan 16 Task 33 — Settings Repair-config dialog (diagnostic + apply).
  "brain_repair_config",
  "brain_repair_config_apply",
] as const;

export type ToolName = (typeof ALL_TOOL_NAMES)[number];
