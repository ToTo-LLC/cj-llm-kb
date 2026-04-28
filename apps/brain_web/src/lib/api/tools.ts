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

export interface RecentEntry {
  path: string;
  title: string;
  modified: string; // ISO-8601 timestamp
  domain: string;
}

export interface PendingPatch {
  patch_id: string;
  target_path: string;
  reason: string;
  created_at: string; // ISO-8601 timestamp
  [extra: string]: unknown; // envelope may carry extra tool-specific fields
}

export interface RecentIngestEntry {
  source: string;
  domain: string | null;
  status: string;
  at: string;
  [extra: string]: unknown;
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

/** Read ``<domain>/index.md``. ``domain`` defaults to the first allowed domain. */
export const getIndex = (
  args: { domain?: string } = {},
): Promise<ToolResponse<{ path: string; content: string }>> =>
  callTool<{ path: string; content: string }>("brain_get_index", args);

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

/** Fetch the top-level ``BRAIN.md`` meta-index. */
export const getBrainMd = (): Promise<
  ToolResponse<{ path: string; content: string }>
> =>
  callTool<{ path: string; content: string }>("brain_get_brain_md");

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

/** Run lint checks across a domain (or every allowed domain if omitted). */
export const lint = (
  args: { domain?: string } = {},
): Promise<
  ToolResponse<{
    findings: Array<Record<string, unknown>>;
    [extra: string]: unknown;
  }>
> =>
  callTool<{
    findings: Array<Record<string, unknown>>;
    [extra: string]: unknown;
  }>("brain_lint", args);

/** Read a single config key. */
export const configGet = (args: {
  key: string;
}): Promise<ToolResponse<{ key: string; value: unknown }>> =>
  callTool<{ key: string; value: unknown }>("brain_config_get", args);

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

// ---------- Plan 07 Task 4 additions (4) ----------

/** Recently ingested sources (feeds the inbox). */
export const recentIngests = (
  args: { limit?: number } = {},
): Promise<ToolResponse<{ items: RecentIngestEntry[] }>> =>
  callTool<{ items: RecentIngestEntry[] }>("brain_recent_ingests", args);

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
] as const;

export type ToolName = (typeof ALL_TOOL_NAMES)[number];
