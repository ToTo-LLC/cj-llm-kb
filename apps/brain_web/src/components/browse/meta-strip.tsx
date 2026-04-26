"use client";

import * as React from "react";
import { Check, Edit, ExternalLink } from "lucide-react";

import { buildObsidianUri } from "@/lib/vault/obsidian-url";
import { cn } from "@/lib/utils";
import { prefetchMonaco } from "./monaco-editor";

/**
 * MetaStrip (Plan 07 Task 18).
 *
 * The thin header above the reader body: domain chip + "folder ·
 * N min read · modified Xd ago" + Obsidian link + Edit/Preview
 * toggle. Lives inside the reader column so it scrolls with the
 * note, not the shell.
 */

export interface MetaStripProps {
  domain: string;
  folder: string;
  readTimeMin: number;
  modifiedAt: string; // ISO-8601 timestamp
  /** Vault-relative path — feeds the Obsidian URI. */
  path: string;
  /** Vault name from ``brain_config_get("vault_name")`` — Task 25
   *  sweep threads the real value through; for now callers can
   *  pass the basename of the vault root. */
  vaultName: string;
  editing: boolean;
  onToggleEdit: () => void;
}

function formatModified(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  const diffMs = Date.now() - d.getTime();
  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 14) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 8) return `${weeks}w ago`;
  return d.toLocaleDateString();
}

export function MetaStrip({
  domain,
  folder,
  readTimeMin,
  modifiedAt,
  path,
  vaultName,
  editing,
  onToggleEdit,
}: MetaStripProps): React.ReactElement {
  const obsidianUri = buildObsidianUri(vaultName, path);
  return (
    <div className="meta-strip flex items-center gap-2 border-b border-[var(--hairline)] px-5 py-2 text-xs text-[var(--text-muted)]">
      <span
        className="chip inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium text-[var(--text)]"
        style={{ background: `var(--dom-${domain}-soft)` }}
      >
        {domain}
      </span>
      <span>
        {folder} · {readTimeMin} min read · modified{" "}
        {formatModified(modifiedAt)}
      </span>
      <span className="ml-auto" />
      <a
        href={obsidianUri}
        className="obs-link inline-flex items-center gap-1 rounded border border-[var(--hairline)] px-2 py-1 text-[11px] hover:bg-[var(--surface-3)]"
        title="Open in Obsidian"
      >
        <ExternalLink size={12} />
        <span>Obsidian</span>
      </a>
      <button
        type="button"
        onClick={onToggleEdit}
        // Issue #13: prefetch the Monaco chunk on hover/focus so the
        // editor is warm by the time the click lands. ``prefetchMonaco``
        // is idempotent — fired on every hover but only one network
        // round-trip happens per session. Skipped while ``editing`` is
        // true because the chunk has already loaded.
        onMouseEnter={editing ? undefined : prefetchMonaco}
        onFocus={editing ? undefined : prefetchMonaco}
        className={cn(
          "edit-toggle inline-flex items-center gap-1 rounded border border-[var(--hairline)] px-2 py-1 text-[11px] hover:bg-[var(--surface-3)]",
          editing && "bg-[var(--surface-3)] text-[var(--text)]",
        )}
      >
        {editing ? (
          <>
            <Check size={12} /> Preview
          </>
        ) : (
          <>
            <Edit size={12} /> Edit
          </>
        )}
      </button>
    </div>
  );
}
