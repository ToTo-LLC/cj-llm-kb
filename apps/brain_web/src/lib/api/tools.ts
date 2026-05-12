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

/**
 * List recently modified notes.
 *
 * Mirrors the `brain_recent` backend handler outer shape
 * (`packages/brain_core/src/brain_core/tools/recent.py:63`); backend emits
 * `{items, limit_used}`. Plan 19 T4.1 widened this TS interface from the
 * pre-fix `{items}` shape — `limit_used` (the clamped effective limit per
 * the `_MAX_LIMIT=50` ceiling) was always emitted but TS had no place
 * for it. Cosmetic-severity widen (no live consumer read the field;
 * Plan 18 T2 audit deferred to Plan 19 Track C bundle).
 */
export const recent = (
  args: { domain?: string; limit?: number } = {},
): Promise<ToolResponse<{ items: RecentEntry[]; limit_used: number }>> =>
  callTool<{ items: RecentEntry[]; limit_used: number }>("brain_recent", args);

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

/**
 * Discriminated by `status`. Three branches, mirroring the backend handler
 * at ``packages/brain_core/src/brain_core/tools/ingest.py:161-217``:
 *  - ``"applied"``: vault written autonomously; ``note_path`` set.
 *  - ``"pending"``: patch staged for approval; ``patch_id`` + ``target_path`` set.
 *  - ``"quarantined" | "failed" | "skipped_duplicate"``: error/skip branch;
 *    ``errors`` list set; ``note_path`` may be present for partial extraction.
 *
 * Plan 18 T3.5: TS interface narrowed from the pre-fix ``{patch_id, applied,
 * domain, [extra]}`` shape (which never matched any backend branch — ``applied``
 * and ``domain`` were never emitted, ``patch_id`` was only in the pending
 * branch). Backend is source of truth.
 *
 * NOTE: there is an unrelated ``IngestStatus`` exported from
 * ``lib/state/inbox-store.ts`` (a 7-value UI-internal lifecycle enum). The
 * backend-status union here is kept inline in the variants to avoid the
 * name collision.
 */
export type IngestResultData =
  | { status: "applied"; note_path: string }
  | { status: "pending"; patch_id: string; target_path: string }
  | {
      status: "quarantined" | "failed" | "skipped_duplicate";
      errors: string[];
      note_path: string | null;
    };

/** Ingest a URL, file path, or raw text. Default stages a patch. */
export const ingest = (args: {
  source: string;
  autonomous?: boolean;
  domain_override?: string;
}): Promise<ToolResponse<IngestResultData>> =>
  callTool<IngestResultData>("brain_ingest", args);

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

/** One item in the planned branch's ``items`` array. */
export interface BulkImportPlannedItem {
  path: string;
  slug: string;
  classified_domain: string;
  confidence: number;
}

/** One row in the applied branch's ``failed`` array. */
export interface BulkImportFailedRow {
  path: string;
  errors: string[];
}

/**
 * Discriminated by ``status``. Three branches, mirroring the backend
 * handler at ``packages/brain_core/src/brain_core/tools/bulk_import.py:150-241``:
 *  - ``"refused"``: folder exceeded the large-folder threshold without an
 *    explicit ``max_files`` cap; ONLY reachable when ``dry_run=false``.
 *  - ``"planned"``: dry-run succeeded; ``items`` lists the per-file plan.
 *    ``dry_run=true`` callers always land here (or surface an exception).
 *  - ``"applied"``: real apply succeeded; the 4 result arrays partition
 *    the input set by per-file outcome.
 *
 * Plan 18 T3.9 narrowed this TS interface from the pre-fix
 * ``{plan: Array<Record<string, unknown>>, applied: boolean, [extra]}``
 * shape (which never matched any backend branch — ``plan`` was never
 * emitted; ``applied`` was emitted as ``string[]`` not ``boolean``). The
 * ``step-pick-folder.tsx`` consumer's pre-fix workaround cast
 * (``as { items?: unknown }``) is now eliminated — the typed
 * discriminated union handles narrowing directly.
 */
export type BulkImportData =
  | { status: "refused"; reason: string; file_count: number }
  | {
      status: "planned";
      file_count: number;
      skipped_count: number;
      items: BulkImportPlannedItem[];
    }
  | {
      status: "applied";
      applied: string[];
      quarantined: string[];
      duplicate: string[];
      failed: BulkImportFailedRow[];
    };

/** Bulk-import a folder. ``dry_run`` defaults to true. */
export const bulkImport = (args: {
  folder: string;
  dry_run?: boolean;
  max_files?: number;
}): Promise<ToolResponse<BulkImportData>> =>
  callTool<BulkImportData>("brain_bulk_import", args);

// ---------- write / patch tools (5) ----------

/**
 * Stage a new note for approval.
 *
 * Mirrors the `brain_propose_note` backend handler
 * (`packages/brain_core/src/brain_core/tools/propose_note.py:94-98`);
 * backend emits `{status: "pending", patch_id, target_path}`. Plan 19 T4.2
 * widened this TS interface from the pre-fix `{patch_id, target_path}`
 * shape — `status` was always emitted but TS had no place for it.
 * Cosmetic-severity widen (no live consumer read the field; Plan 18 T2
 * audit deferred to Plan 19 Track C bundle).
 */
export const proposeNote = (args: {
  path: string;
  content: string;
  reason: string;
}): Promise<
  ToolResponse<{ status: string; patch_id: string; target_path: string }>
> =>
  callTool<{ status: string; patch_id: string; target_path: string }>(
    "brain_propose_note",
    args,
  );

/**
 * List pending patches in the approval queue.
 *
 * Mirrors the `brain_list_pending_patches` backend handler
 * (`packages/brain_core/src/brain_core/tools/list_pending_patches.py:54`);
 * backend emits `{count, patches}`. Plan 19 T4.3 widened this TS interface
 * from the pre-fix `{patches}` shape — `count` (the rendered envelope
 * count, equal to `patches.length`) was always emitted but TS had no
 * place for it. Cosmetic-severity widen (no live consumer read the
 * field; Plan 18 T2 audit deferred to Plan 19 Track C bundle).
 */
export const listPendingPatches = (
  args: { limit?: number } = {},
): Promise<ToolResponse<{ count: number; patches: PendingPatch[] }>> =>
  callTool<{ count: number; patches: PendingPatch[] }>(
    "brain_list_pending_patches",
    args,
  );

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

/**
 * Reject a staged patch with a human-readable reason.
 *
 * Mirrors the `brain_reject_patch` backend handler (see
 * `packages/brain_core/src/brain_core/tools/reject_patch.py`). Backend
 * has a single branch — `data = {status: "rejected", patch_id, reason}` —
 * with the `reason` being the same human-readable string the caller
 * supplied as input (now persisted to the rejected envelope on disk).
 * Plan 18 T3.6 narrowed this TS interface from the pre-fix
 * `{patch_id, rejected: boolean}` shape (which never matched backend —
 * `rejected: boolean` was plan-author drift from an earlier sketch
 * that never landed).
 */
export const rejectPatch = (args: {
  patch_id: string;
  reason: string;
}): Promise<
  ToolResponse<{ status: "rejected"; patch_id: string; reason: string }>
> =>
  callTool<{ status: "rejected"; patch_id: string; reason: string }>(
    "brain_reject_patch",
    args,
  );

/**
 * Revert the most recent applied write (or a specific `undo_id`).
 *
 * Mirrors the `brain_undo_last` backend handler (see
 * `packages/brain_core/src/brain_core/tools/undo_last.py`); two branches
 * discriminated by `status`:
 *  - `"reverted"`: an undo record was found and reverted — `undo_id`
 *    identifies which record was rolled back.
 *  - `"nothing_to_undo"`: no undo history existed (empty/missing
 *    `<vault>/.brain/undo/`); the caller should treat this as a no-op
 *    rather than an error.
 *
 * Plan 18 T3.7 narrowed this TS interface from the pre-fix
 * `{undo_id, reverted_files: string[], [extra]}` shape (which never
 * matched backend — `reverted_files` was plan-author drift that never
 * landed; the consumer toast at `pending-screen.tsx` was reading the
 * missing field and always showing "Reverted 0 file(s)." — fixed in
 * the same commit).
 */
export type UndoLastData =
  | { status: "reverted"; undo_id: string }
  | { status: "nothing_to_undo" };

export const undoLast = (
  args: { undo_id?: string } = {},
): Promise<ToolResponse<UndoLastData>> =>
  callTool<UndoLastData>("brain_undo_last", args);

// ---------- maintenance tools (4) ----------

/**
 * Summarise spend-to-date.
 *
 * Mirrors the `brain_cost_report` backend handler (see
 * `packages/brain_core/src/brain_core/tools/cost_report.py`); single
 * branch — always emits `{today_usd, month_usd, by_domain, by_mode}`.
 * `by_domain` and `by_mode` are dicts keyed by domain slug / chat mode
 * string respectively (the "" key in `by_mode` captures NULL-mode
 * rows — ingest / legacy — and the frontend renders that as "Other"
 * per the backend's Plan 07 Task 3 comment).
 *
 * Plan 18 T3.8 narrowed this TS interface from the pre-fix
 * `{total_usd, by_operation, [extra]}` shape (which never matched
 * backend — both TS-required fields were plan-author drift from an
 * earlier sketch that never landed). No active consumer at the time
 * of the narrow.
 */
export const costReport = (): Promise<
  ToolResponse<{
    today_usd: number;
    month_usd: number;
    by_domain: Record<string, number>;
    by_mode: Record<string, number>;
  }>
> =>
  callTool<{
    today_usd: number;
    month_usd: number;
    by_domain: Record<string, number>;
    by_mode: Record<string, number>;
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

/**
 * Write a single config key. ``value`` is validated server-side.
 *
 * Mirrors the `brain_config_set` backend handler
 * (`packages/brain_core/src/brain_core/tools/config_set.py:832-845, 901-910`);
 * backend emits `{status, key, value, persisted, note}` from BOTH branches
 * (persisted Config-field path AND non-persisted session-scoped path) —
 * `persisted: boolean` is the discriminator and `note` carries the
 * human-readable disposition. Plan 19 T4.4 widened this TS interface
 * from the pre-fix `{key, value}` shape — three keys (`status`,
 * `persisted`, `note`) were always emitted but TS had no place for them.
 * Cosmetic-severity widen (no live consumer read the fields; Plan 18 T2
 * audit deferred to Plan 19 Track C bundle).
 *
 * The widened shape propagates to the 7 `configSet`-routed wrappers
 * (`setDomainOverride`, `setPrivacyRailed`, `setDomainBudget`,
 * `setDomainRateLimit`, `setDomainAutonomy`, `setActiveDomain`,
 * `setCrossDomainWarningAcknowledged`) — each wrapper's return type
 * now references `ConfigSetData` directly so callers see the same
 * five-field shape on hover regardless of which wrapper they invoke.
 * Plan 19 T4 deliberately uses the named interface (not a structural
 * `{status, key, value, persisted, note}` inlined at every site) so a
 * future backend shape change ripples through one type alias rather
 * than 8 wrapper signatures.
 */
export interface ConfigSetData {
  status: string;
  key: string;
  value: unknown;
  persisted: boolean;
  note: string;
}

export const configSet = (args: {
  key: string;
  value: unknown;
}): Promise<ToolResponse<ConfigSetData>> =>
  callTool<ConfigSetData>("brain_config_set", args);

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
}): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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
): Promise<ToolResponse<ConfigSetData>> =>
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

/**
 * Create a new domain with a slug, display name, and accent colour.
 *
 * Mirrors the `brain_create_domain` backend handler (see
 * `packages/brain_core/src/brain_core/tools/create_domain.py`). Single
 * branch on success — invalid/existing slugs raise exceptions (not
 * alternate-shape error branches). The new domain's fields are nested
 * under `domain` in the backend payload; Plan 18 T3.10 narrowed this
 * TS interface from the pre-fix top-level `{slug, name, accent_color}`
 * shape (which never matched backend — top-level reads were all
 * `undefined`) to the real nested shape.
 */
export const createDomain = (args: {
  slug: string;
  name: string;
  accent_color?: string;
}): Promise<
  ToolResponse<{
    status: "created";
    domain: { slug: string; name: string; accent_color: string };
    note: string;
  }>
> =>
  callTool<{
    status: "created";
    domain: { slug: string; name: string; accent_color: string };
    note: string;
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

/**
 * Temporarily bump the cost-budget ceiling by `amount_usd` for
 * `duration_hours` hours.
 *
 * Mirrors the `brain_budget_override` backend handler (see
 * `packages/brain_core/src/brain_core/tools/budget_override.py`). Single
 * branch on success — out-of-range inputs raise exceptions, not
 * alternate-shape error branches.
 *
 * Plan 18 T3.11 narrowed this TS interface from the pre-fix
 * `{amount_usd, duration_hours, expires_at, [extra]}` shape (which
 * never matched backend — all three TS-required fields were renames
 * of backend fields or echoes of INPUT-only args). `override_until`
 * carries the ISO-8601 timestamp when the override expires;
 * `override_delta_usd` is the dollar amount added to the daily cap
 * (semantically the same as the caller's `amount_usd` input).
 */
export const budgetOverride = (args: {
  amount_usd: number;
  duration_hours?: number;
}): Promise<
  ToolResponse<{
    status: "override_set";
    override_until: string;
    override_delta_usd: number;
    note: string;
  }>
> =>
  callTool<{
    status: "override_set";
    override_until: string;
    override_delta_usd: number;
    note: string;
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

// ---------- Plan 22 — Watched folders (3 tools) ----------

/**
 * One row in :func:`listWatchedFolders`'s response. Mirrors the backend
 * ``brain_list_watched_folders`` handler's per-entry dict exactly (see
 * ``packages/brain_core/src/brain_core/tools/list_watched_folders.py:96-106``).
 *
 * The keys are pinned by ``test_list_watched_folders.py``'s
 * ``test_data_shape_pin_with_one_folder`` (Plan 22 T5) — drift on either
 * side fails RED on the Python pin, so the TS interface stays in lock-
 * step with the wire shape.
 *
 * - ``path`` — absolute folder path on disk (string, not URL).
 * - ``domain`` — target domain slug. When the user picked "lazy classify"
 *   at watch-enable time, this lands on the first non-personal
 *   configured domain (see ``watch_folder.py:252-267``); the per-file
 *   classifier is the real domain decider for the initial sync.
 * - ``enabled`` — whether the watcher fires on file events for this
 *   folder. Plan 22 v1 always sets ``true`` on watch-enable; the Settings
 *   toggle's OFF path goes through the watch-disable modal (which calls
 *   :func:`unwatchFolder` rather than flipping ``enabled``).
 * - ``last_sync`` — ISO-8601 timestamp of the most recent successful sync,
 *   or ``null`` when the folder was watched but no sync has run yet
 *   (e.g. ``initial_sync=false``). Frontend renders "never synced" /
 *   "Pending initial sync…" for this state.
 * - ``policy`` — currently always ``"overwrite"`` (Plan 22 D1: source is
 *   canonical, vault edits to watched notes are overwritten on next
 *   sync). Future policies (e.g. ``"merge"``) would land here.
 * - ``include_subdirs`` — whether the watcher recurses into subdirectories.
 *   Defaults to ``true`` at watch-enable; surfaced as a checkbox in the
 *   row so users can flip it post-hoc (writes route through the watch-
 *   enable modal's re-watch flow in T15).
 * - ``file_count`` — number of vault notes whose frontmatter
 *   ``watched_folder_id`` matches this entry's ``path``. Walked at request
 *   time (no cache).
 * - ``orphan_count`` — subset of ``file_count`` whose frontmatter
 *   ``orphaned == true``. Walked at request time.
 */
export interface WatchedFolderEntry {
  path: string;
  domain: string;
  enabled: boolean;
  last_sync: string | null;
  policy: string;
  include_subdirs: boolean;
  file_count: number;
  orphan_count: number;
}

/**
 * ``brain_list_watched_folders`` ``ToolResult.data`` shape. Single key
 * (``folders``) holding the array — wraps the list in a struct so the
 * outer envelope has room to grow (e.g. a future ``stats`` summary)
 * without a breaking shape change. Plan 22 T12: the Settings panel's
 * single data source — `WatchedFolderRow` consumers and the (future)
 * topbar status indicator (T14) read off the same shape.
 */
export interface ListWatchedFoldersData {
  folders: WatchedFolderEntry[];
}

/**
 * List every watched folder in :attr:`Config.watched_folders` with the
 * runtime stats (file_count, orphan_count, last_sync) walked from the
 * vault. Read-only. Safe to call without ``typed_confirm``.
 *
 * The Settings → Watched folders panel (Plan 22 T12) calls this on
 * first mount and after every mutation (watch / unwatch / resync) so
 * the row list stays canonical with the backend.
 */
export const listWatchedFolders = (): Promise<
  ToolResponse<ListWatchedFoldersData>
> =>
  callTool<ListWatchedFoldersData>("brain_list_watched_folders");

/**
 * Cost-estimate payload returned by ``brain_watch_folder`` (in both
 * dry-run and real-run branches when ``initial_sync`` is ``true``).
 *
 * Mirrors the backend handler at
 * ``packages/brain_core/src/brain_core/tools/watch_folder.py:328-333,
 *  399-404`` (the dict literal is built in two places that produce the
 * exact same shape; T14.5 pinned this). Plan 22 D3 specifies the
 * estimate is informational only — there is NO refusal threshold —
 * so the modal renders the panel and lets the user proceed.
 *
 *  - ``file_count`` — number of source files the initial-sync walker
 *    would classify (recursive walk respects ``include_subdirs``).
 *  - ``estimated_tokens`` — file_count × per-file classify token cost
 *    (T14.5's ``_CLASSIFY_TOKEN_COST`` constant). The summarize +
 *    integrate spend is NOT included — that's per-file post-classify
 *    and depends on each file's body length.
 *  - ``estimated_usd`` — input × pricing lookup for the
 *    ``classify_model``. ``null`` when the pricing table has no entry
 *    for the resolved model (forward-compat for a model swap that
 *    lands ahead of pricing); the modal renders "n/a (no pricing
 *    entry)" in that branch.
 *  - ``classify_model`` — the resolved model id the cost estimate is
 *    keyed on; the modal surfaces this so the user can see WHICH
 *    model the projection is for.
 */
export interface WatchFolderCostEstimate {
  file_count: number;
  estimated_tokens: number;
  estimated_usd: number | null;
  classify_model: string;
}

/**
 * ``brain_watch_folder`` ``ToolResult.data`` shape. Three branches
 * discriminated by ``status`` — mirrors the backend handler at
 * ``packages/brain_core/src/brain_core/tools/watch_folder.py:265-278,
 *  351-363, 471-489``:
 *
 *  - ``"dry_run"``: T14.5 cost-estimate preview; NO state mutated.
 *    Caller hands the same args back with ``dry_run=false`` to confirm.
 *    ``cost_estimate`` is populated when ``initial_sync=true`` (the
 *    common case from the modal); ``null`` when ``initial_sync=false``.
 *  - ``"watched"``: real-run success; the folder is now in
 *    ``Config.watched_folders``. ``initial_sync_summary`` carries the
 *    per-file counts when the initial sync ran; ``null`` when
 *    ``initial_sync=false``. ``cost_estimate`` mirrors the same shape
 *    as the dry-run branch (the value the user saw at confirm time).
 *  - ``"already_watched"``: idempotent no-op; the folder was already
 *    in ``Config.watched_folders``. ``initial_sync_summary`` is always
 *    ``null`` here (no sync ran); ``cost_estimate`` is always ``null``
 *    (no spend to project).
 */
export type WatchFolderData =
  | {
      status: "dry_run";
      folder: string;
      domain: string;
      initial_sync_summary: null;
      cost_estimate: WatchFolderCostEstimate | null;
    }
  | {
      status: "watched";
      folder: string;
      domain: string;
      initial_sync_summary: {
        planned: number;
        applied: number;
        skipped_duplicate: number;
        failed: number;
      } | null;
      cost_estimate: WatchFolderCostEstimate | null;
    }
  | {
      status: "already_watched";
      folder: string;
      domain: string;
      initial_sync_summary: null;
      cost_estimate: null;
    };

/**
 * Register a watched folder + optionally run the initial sync (Plan 22
 * T5 / T14.5).
 *
 *  - ``folder`` — absolute path on disk.
 *  - ``domain`` — explicit target domain slug (omit for lazy classify,
 *    which lets the per-file classifier route each note at sync time).
 *  - ``include_subdirs`` — recurse into subfolders. Defaults to ``true``
 *    server-side; modal defaults match.
 *  - ``initial_sync`` — fire the bulk-import sync immediately. Defaults
 *    to ``true`` server-side; the watch-enable modal always passes
 *    ``true``.
 *  - ``dry_run`` — Plan 22 T14.5 cost-preview mode. ``true`` returns
 *    the cost estimate WITHOUT mutating config / backups / vault;
 *    ``false`` commits the watch + runs the initial sync.
 *
 * The watch-enable modal calls this twice: once on mount with
 * ``dry_run=true`` to populate the cost panel; once on confirm with
 * ``dry_run=false`` to commit.
 */
export const watchFolder = (args: {
  folder: string;
  domain?: string;
  include_subdirs?: boolean;
  initial_sync?: boolean;
  dry_run?: boolean;
}): Promise<ToolResponse<WatchFolderData>> =>
  callTool<WatchFolderData>("brain_watch_folder", args);

/**
 * ``brain_unwatch_folder`` ``ToolResult.data`` shape. Two branches
 * discriminated by ``status`` — mirrors the backend handler at
 * ``packages/brain_core/src/brain_core/tools/unwatch_folder.py:92-122``:
 *
 *  - ``"unwatched"``: the matching entry was removed from
 *    ``Config.watched_folders``; ``remaining_notes`` counts vault notes
 *    whose frontmatter ``watched_folder_id`` matches (those notes are
 *    intentionally left in place per Plan 22 D2 — the user adjudicates
 *    them via the Orphans tab).
 *  - ``"not_watched"``: idempotent no-op; the folder wasn't in the
 *    config to begin with. ``remaining_notes`` still walks the vault so
 *    the caller can surface the same advisory count.
 */
export type UnwatchFolderData =
  | {
      status: "unwatched";
      folder: string;
      remaining_notes: number;
    }
  | {
      status: "not_watched";
      folder: string;
      remaining_notes: number;
    };

/**
 * Remove a watched folder entry from :attr:`Config.watched_folders`.
 * Non-destructive (Plan 22 D2): existing vault notes stay on disk;
 * orphans remain marked. Idempotent on a folder that isn't watched.
 *
 * The Settings → Watched folders panel calls this from the row's
 * "Unwatch" action (after the watch-disable confirmation modal — T15).
 */
export const unwatchFolder = (args: {
  folder: string;
}): Promise<ToolResponse<UnwatchFolderData>> =>
  callTool<UnwatchFolderData>("brain_unwatch_folder", args);

/**
 * ``brain_resync_folder`` ``ToolResult.data`` shape. Pinned by
 * ``packages/brain_core/tests/tools/test_resync_folder.py`` —
 * ``test_data_shape_pin_empty_folder`` asserts the exact key set
 * (``status / folder / summary``) with the four summary counts
 * (``updated`` / ``no_change`` / ``newly_orphaned`` /
 * ``restored_from_orphan``). Drift on either side fails RED on the
 * Python pin, so the TS interface stays in lock-step with the wire
 * shape.
 *
 * Single branch on success (``status: "resynced"``). Failure modes
 * (relative-path / missing-folder / unwatched-folder) raise exceptions
 * server-side, not alternate-shape error branches — the wrapper
 * surfaces them as :class:`ApiError` rejections (Plan 22 T12 fix-up
 * docs the matching toast at the panel's call site).
 *
 *  - ``updated`` — vault notes whose source file changed since the
 *    last sync; content overwritten this run.
 *  - ``no_change`` — vault notes whose source file content_hash
 *    matched the cached value; skipped.
 *  - ``newly_orphaned`` — vault notes whose source file disappeared
 *    since the last sync; frontmatter ``orphaned: true`` flipped on.
 *  - ``restored_from_orphan`` — vault notes that were previously
 *    orphaned but whose source file reappeared; orphan flag cleared.
 */
export interface ResyncFolderData {
  status: "resynced";
  folder: string;
  summary: {
    updated: number;
    no_change: number;
    newly_orphaned: number;
    restored_from_orphan: number;
  };
}

/**
 * Force a re-walk + re-ingest of every file under a watched folder
 * (Plan 22 T5). Updates vault notes whose source content_hash changed,
 * flags as orphan any vault note whose source file disappeared, and
 * restores the orphan flag on notes whose source reappeared.
 *
 * The Settings → Watched folders panel calls this from the row's
 * "Resync now" action (Plan 22 T12 fix-up — the earlier T12 mistakenly
 * disabled the button on the false claim that the backend tool didn't
 * ship in T5; it did. Wiring is now correct).
 *
 * Refuses non-absolute paths, missing paths, or paths that aren't in
 * :attr:`Config.watched_folders` (server-side ``ValueError`` /
 * ``FileNotFoundError`` — surfaced as :class:`ApiError` rejections).
 */
export const resyncFolder = (args: {
  folder: string;
}): Promise<ToolResponse<ResyncFolderData>> =>
  callTool<ResyncFolderData>("brain_resync_folder", args);

// ---------- Plan 22 T13 — Orphan management (3 tools) ----------

/**
 * One row in :func:`listOrphans`'s response. Mirrors the backend
 * ``brain_list_orphans`` handler's per-entry dict exactly (see
 * ``packages/brain_core/src/brain_core/tools/list_orphans.py``).
 *
 * Keys pinned by ``test_list_orphans.py`` /
 * ``test_returns_only_orphaned_notes_data_shape_pin`` (Plan 22 T5) —
 * drift on either side fails RED on the Python pin, so the TS interface
 * stays in lock-step with the wire shape.
 *
 *  - ``note_path`` — absolute path of the vault note that is marked as
 *    orphaned. The Orphans panel uses this as the row key and passes it
 *    to ``brain_restore_orphan`` / ``brain_delete_orphan``.
 *  - ``domain`` — domain slug derived from the note's vault path. Used
 *    by the Settings → Orphans panel to render the per-row domain badge.
 *  - ``source_path`` — last-known source path from the note's
 *    ``source_path`` frontmatter key. The mockup renders this as a
 *    monospace sub-line so the user can recognise where the source
 *    file lived. May be the empty string if the frontmatter is missing
 *    the key.
 *  - ``orphaned_at`` — ISO-8601 timestamp recorded in frontmatter when
 *    the note was first marked orphaned. Used for the "Orphaned ${relative}"
 *    label.
 *  - ``watched_folder_id`` — the watched folder root that originally
 *    ingested this note (frontmatter ``watched_folder_id`` key). The
 *    Settings → Orphans panel groups rows by this value (mockup §"Group
 *    separator").
 */
export interface OrphanEntry {
  note_path: string;
  domain: string;
  source_path: string;
  orphaned_at: string;
  watched_folder_id: string;
}

/**
 * ``brain_list_orphans`` ``ToolResult.data`` shape. Single key
 * (``orphans``) holding the array — wraps the list in a struct so the
 * outer envelope has room to grow (e.g. a future ``total`` summary
 * count) without a breaking shape change.
 */
export interface ListOrphansData {
  orphans: OrphanEntry[];
}

/**
 * List every orphaned note in the vault. Optionally filters to a single
 * ``watched_folder_id`` via the ``folder`` argument; omit for the
 * full list.
 *
 * The Settings → Orphans panel (Plan 22 T13) calls this on first mount
 * and after every mutation (restore / delete) so the row list stays
 * canonical with the backend.
 */
export const listOrphans = (
  args: { folder?: string } = {},
): Promise<ToolResponse<ListOrphansData>> =>
  callTool<ListOrphansData>("brain_list_orphans", args);

/**
 * ``brain_restore_orphan`` ``ToolResult.data`` shape. Pinned by
 * ``test_restore_orphan.py`` / ``test_data_shape_pin_and_flips_frontmatter``
 * (Plan 22 T5) — single branch on success (``status: "restored"``).
 *
 * Failure modes (relative-path, missing note, non-orphan note) raise
 * exceptions server-side, not alternate-shape error branches — the
 * wrapper surfaces them as :class:`ApiError` rejections (Plan 22 T13
 * documents the matching toast at the panel's call site).
 */
export interface RestoreOrphanData {
  status: "restored";
  note_path: string;
  undo_id: string;
}

/**
 * Restore an orphaned vault note (clear the ``orphaned: true``
 * frontmatter flag). The source file may or may not still be missing —
 * the next watched-folder sync re-marks the note if the source is
 * still gone. Reversible via :func:`undoLast`.
 *
 * The Settings → Orphans panel calls this from the per-row "Restore"
 * action and from the bulk "Restore selected" action (one call per
 * selected row).
 */
export const restoreOrphan = (args: {
  note_path: string;
}): Promise<ToolResponse<RestoreOrphanData>> =>
  callTool<RestoreOrphanData>("brain_restore_orphan", args);

/**
 * ``brain_delete_orphan`` ``ToolResult.data`` shape. Pinned by
 * ``test_delete_orphan.py`` / ``test_data_shape_pin_happy_path``
 * (Plan 22 T5) — single branch on success (``status: "deleted"``).
 *
 * The backend REFUSES unless the caller passes ``typed_confirm: true``
 * (CLAUDE.md "destructive action requires typed confirmation" rule —
 * see ``test_refuses_without_typed_confirm`` / ``test_refuses_with_typed_confirm_false``).
 * The frontend gates this through ``TypedConfirmDialog`` (single-note:
 * type the slug; bulk: type ``delete N notes``).
 *
 *  - ``trash_path`` — absolute path under
 *    ``<vault>/.brain/trash/<YYYY-MM-DD>/`` where the note's content
 *    was moved. Preserved as an audit trail.
 *  - ``undo_id`` — identifier the user can pass to
 *    :func:`undoLast` (or ``brain_undo_last``) to recreate the note at
 *    its original path.
 */
export interface DeleteOrphanData {
  status: "deleted";
  trash_path: string;
  undo_id: string;
}

/**
 * Permanently move an orphaned vault note to ``.brain/trash/``.
 * REQUIRES ``typed_confirm: true`` — the backend raises
 * :class:`PermissionError` otherwise (CLAUDE.md destructive-action rule
 * mirrored by :func:`brainDeleteDomain`).
 *
 * The Settings → Orphans panel calls this from the per-row "Delete"
 * action (after the single-note typed-confirm modal) and from the bulk
 * "Delete selected" action (one call per selected row, after a single
 * batch typed-confirm modal — see ``modal-orphan-delete.md`` §Bulk mode).
 *
 * Reversible via :func:`undoLast` — the response carries the
 * ``undo_id`` for the recovery path.
 */
export const deleteOrphan = (args: {
  note_path: string;
  typed_confirm: boolean;
}): Promise<ToolResponse<DeleteOrphanData>> =>
  callTool<DeleteOrphanData>("brain_delete_orphan", args);

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
  // Plan 22 — Watched folders (live source → vault sync). T12 wired the
  // panel-facing read + unwatch tools; the T12 fix-up wires
  // ``brain_resync_folder`` (the prior T12 mistakenly disabled the
  // "Resync now" button on the false claim that the backend handler
  // didn't ship in T5; it did — see
  // ``packages/brain_core/src/brain_core/tools/resync_folder.py``).
  // T13 wires the orphan-management tools (list/restore/delete).
  // T15 wires ``brain_watch_folder`` (watch-enable modal — dry-run cost
  // preview + real-run commit).
  "brain_list_watched_folders",
  "brain_watch_folder",
  "brain_unwatch_folder",
  "brain_resync_folder",
  "brain_list_orphans",
  "brain_restore_orphan",
  "brain_delete_orphan",
] as const;

export type ToolName = (typeof ALL_TOOL_NAMES)[number];
