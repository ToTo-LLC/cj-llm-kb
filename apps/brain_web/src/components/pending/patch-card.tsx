"use client";

import * as React from "react";
import { Bell, Check, Edit as EditIcon, Lock, X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * PatchCard (Plan 07 Task 16).
 *
 * Metadata-only row rendered inside the pending screen's left list and
 * (in rail mode) inside the chat-route right rail. Plan 04's hard rule
 * says the list tool never carries the patch body; the body is fetched
 * on-demand when a card is selected, so this component never tries to
 * render diff content.
 *
 * Fields rendered (all metadata):
 *   - Tool name with the ``brain_`` prefix stripped
 *   - Domain chip (lock icon for the ``personal`` domain)
 *   - Created-at relative timestamp
 *   - Target path in monospace
 *   - Reason truncated to ~200 chars (title attribute carries the full text)
 *   - Three inline mini-actions: Approve / Edit / Reject
 *   - Arrival-bell pulse badge when ``isNew`` is set by the WS hook
 *
 * Click → ``onSelect(patch_id)``. Inline action clicks call
 * ``stopPropagation`` so pressing Approve does not also flip the
 * selection.
 *
 * When ``inRail`` is set, actions are hidden (the rail only shows the
 * count + list; the full screen owns interactions).
 */

export interface PatchCardPatch {
  patch_id: string;
  tool: string;
  domain: string;
  target_path: string;
  reason: string;
  created_at: string;
  isNew?: boolean;
}

export interface PatchCardProps {
  patch: PatchCardPatch;
  selected: boolean;
  onSelect: (id: string) => void;
  onApprove: (patch: PatchCardPatch) => void;
  onEdit: (patch: PatchCardPatch) => void;
  onReject: (patch: PatchCardPatch) => void;
  inRail?: boolean;
}

const REASON_MAX = 200;

function stripPrefix(tool: string): string {
  return tool.startsWith("brain_") ? tool.slice("brain_".length) : tool;
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1) + "…";
}

/** Rough relative-time formatter (no dep on date-fns). */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diff = Math.max(0, Date.now() - then);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function PatchCard({
  patch,
  selected,
  onSelect,
  onApprove,
  onEdit,
  onReject,
  inRail = false,
}: PatchCardProps): React.ReactElement {
  const short = stripPrefix(patch.tool);
  const reason = truncate(patch.reason, REASON_MAX);
  const isPersonal = patch.domain === "personal";

  return (
    <div
      role="button"
      tabIndex={0}
      data-new={patch.isNew ? "true" : "false"}
      data-selected={selected ? "true" : "false"}
      onClick={() => onSelect(patch.patch_id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(patch.patch_id);
        }
      }}
      className={cn(
        "patch-card relative cursor-pointer rounded-md border px-3 py-2 text-sm transition-colors",
        "border-[var(--hairline)] bg-[var(--surface-1)] hover:bg-[var(--surface-2)]",
        selected && "border-[var(--accent)] bg-[var(--surface-2)]",
      )}
    >
      {patch.isNew && (
        <span
          aria-label="New"
          title="Proposed just now"
          className={cn(
            "patch-bell absolute right-2 top-2 inline-flex h-5 w-5 items-center justify-center rounded-full",
            "bg-[var(--accent)] text-[10px] font-semibold text-[var(--bg)]",
            "animate-pulse",
          )}
        >
          <Bell className="h-3 w-3" />
        </span>
      )}
      <div className="flex items-center gap-2">
        <span className="p-tool font-medium text-[var(--text)]">{short}</span>
        <span
          className={cn(
            "chip inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]",
            "border-[var(--hairline)] bg-[var(--surface-2)] text-[var(--text-muted)]",
            isPersonal && "text-amber-400",
          )}
          data-domain={patch.domain}
        >
          {isPersonal && <Lock className="h-2.5 w-2.5" />}
          <span>{patch.domain}</span>
        </span>
        <span className="ml-auto text-[10px] text-[var(--text-dim)]">
          {relativeTime(patch.created_at)}
        </span>
      </div>
      <div
        className="mt-1 truncate font-mono text-[11px] text-[var(--text-dim)]"
        title={patch.target_path}
      >
        {patch.target_path}
      </div>
      <div
        className="mt-1 line-clamp-2 text-[12px] text-[var(--text-muted)]"
        title={patch.reason}
      >
        {reason}
      </div>
      {!inRail && (
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-[var(--hairline)] px-2 py-1 text-[11px] hover:bg-[var(--surface-2)]"
            onClick={(e) => {
              e.stopPropagation();
              onApprove(patch);
            }}
          >
            <Check className="h-3 w-3" /> Approve
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-[var(--hairline)] px-2 py-1 text-[11px] hover:bg-[var(--surface-2)]"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(patch);
            }}
          >
            <EditIcon className="h-3 w-3" /> Edit
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-[var(--hairline)] px-2 py-1 text-[11px] text-red-400 hover:bg-[var(--surface-2)]"
            onClick={(e) => {
              e.stopPropagation();
              onReject(patch);
            }}
          >
            <X className="h-3 w-3" /> Reject
          </button>
        </div>
      )}
    </div>
  );
}
