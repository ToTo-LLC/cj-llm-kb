"use client";

import * as React from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  File as FileIcon,
  Folder,
  Lock,
  Search,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { buildTree } from "@/lib/vault/tree";

/**
 * FileTree (Plan 07 Task 18).
 *
 * Groups notes by domain → folder → note, with a collapsible
 * folder header and a clickable note row. Personal-domain notes
 * are hidden when the active scope excludes them, and replaced
 * with a dim "hidden by default" label so the user still knows
 * the domain exists.
 *
 * The top row is a "Search vault…" pseudo-button that opens the
 * SearchOverlay (parent-owned — we just fire ``onOpenSearch``).
 */

export interface FileTreeNote {
  path: string;
  title: string;
  domain: string;
  folder: string;
}

export interface FileTreeProps {
  notes: FileTreeNote[];
  /** Active domain scope. Personal domain only renders notes when
   *  its slug is in the scope. */
  scope: string[];
  /** Currently-selected note path (used to paint the active row). */
  activePath: string | null;
  /** Handler invoked when the "Search vault…" pseudo-button is
   *  clicked. The overlay itself lives at the shell level. */
  onOpenSearch: () => void;
  /** Plan 10 Task 7: live domain slug list. When provided, the tree
   *  also renders headers for configured-but-empty domains so a
   *  fresh ``hobby`` shows up immediately after creation. Omitted
   *  callers fall back to the v0.1 notes-driven grouping. */
  domains?: string[];
}

const PERSONAL_DOMAIN = "personal";

export function FileTree({
  notes,
  scope,
  activePath,
  onOpenSearch,
  domains,
}: FileTreeProps): React.ReactElement {
  const tree = React.useMemo(() => buildTree(notes), [notes]);

  // Plan 10 Task 7: combined domain list = union of (live domains)
  // and (domains seen in notes) so an empty domain still renders a
  // header. We preserve the live-domain order first, then append
  // any note-only domains (shouldn't happen if Config.domains tracks
  // on-disk dirs, but belt-and-braces).
  const renderedDomains = React.useMemo(() => {
    const fromTree = new Map(tree.domains.map((d) => [d.domain, d]));
    if (!domains || domains.length === 0) {
      return tree.domains;
    }
    const out: typeof tree.domains = [];
    const seen = new Set<string>();
    for (const slug of domains) {
      out.push(fromTree.get(slug) ?? { domain: slug, folders: [] });
      seen.add(slug);
    }
    for (const d of tree.domains) {
      if (!seen.has(d.domain)) out.push(d);
    }
    return out;
  }, [tree, domains]);

  // Collapsed folder keys, stored as ``"<domain>/<folder>"``.
  // Default: every folder expanded; click-to-collapse.
  const [collapsed, setCollapsed] = React.useState<Set<string>>(
    () => new Set(),
  );

  const toggleFolder = React.useCallback((key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  return (
    <div className="file-tree flex h-full flex-col gap-2 overflow-y-auto border-r border-[var(--hairline)] bg-[var(--surface-1)] p-2 text-sm text-[var(--text)]">
      <button
        type="button"
        onClick={onOpenSearch}
        className="tree-search flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] px-2 py-1.5 text-left text-xs text-[var(--text-muted)] hover:bg-[var(--surface-3)]"
      >
        <Search size={12} />
        <span>Search vault…</span>
        <span className="ml-auto flex gap-0.5 text-[10px] text-[var(--text-dim)]">
          <kbd className="rounded border border-[var(--hairline)] px-1">⌘</kbd>
          <kbd className="rounded border border-[var(--hairline)] px-1">K</kbd>
        </span>
      </button>

      {renderedDomains.map((dom) => {
        const isPersonal = dom.domain === PERSONAL_DOMAIN;
        const inScope = scope.includes(dom.domain);
        const hidePersonal = isPersonal && !inScope;
        const isEmpty = dom.folders.length === 0;

        return (
          <div key={dom.domain} className="tree-group flex flex-col gap-0.5">
            <div
              data-testid={`domain-header-${dom.domain}`}
              className="tree-head flex items-center gap-2 px-1 pt-2 text-[11px] uppercase tracking-wide text-[var(--text-muted)]"
            >
              <span
                className="dot inline-block h-2 w-2 rounded-full"
                style={{ background: `var(--dom-${dom.domain})` }}
              />
              {isPersonal && <Lock size={10} aria-hidden="true" />}
              <span>{dom.domain}</span>
            </div>

            {hidePersonal ? (
              <div
                className="dim px-3 py-1 text-[11px] italic text-[var(--text-dim)]"
                data-testid="personal-hidden-label"
              >
                — hidden by default
              </div>
            ) : isEmpty ? (
              <div
                className="dim px-3 py-1 text-[11px] italic text-[var(--text-dim)]"
                data-testid={`domain-empty-${dom.domain}`}
              >
                No notes yet
              </div>
            ) : (
              dom.folders.map((fld) => {
                const key = `${dom.domain}/${fld.folder}`;
                const isCollapsed = collapsed.has(key);
                return (
                  <div key={key} className="flex flex-col">
                    <button
                      type="button"
                      aria-expanded={!isCollapsed}
                      aria-label={`${fld.folder} folder`}
                      onClick={() => toggleFolder(key)}
                      className="tree-folder flex items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs text-[var(--text-muted)] hover:bg-[var(--surface-2)]"
                    >
                      {isCollapsed ? (
                        <ChevronRight size={12} />
                      ) : (
                        <ChevronDown size={12} />
                      )}
                      <Folder size={12} />
                      <span>{fld.folder}</span>
                      <span className="ml-auto text-[10px] text-[var(--text-dim)]">
                        {fld.notes.length}
                      </span>
                    </button>
                    {!isCollapsed &&
                      fld.notes.map((note) => {
                        const active = note.path === activePath;
                        return (
                          <Link
                            key={note.path}
                            href={`/browse/${note.path}`}
                            data-testid={`tree-node-${note.path}`}
                            data-active={active ? "true" : "false"}
                            className={cn(
                              "tree-node ml-4 flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs text-[var(--text)] hover:bg-[var(--surface-2)]",
                              active &&
                                "bg-[var(--surface-3)] text-[var(--text)]",
                            )}
                          >
                            <FileIcon size={11} />
                            <span className="truncate">{note.title}</span>
                          </Link>
                        );
                      })}
                  </div>
                );
              })
            )}
          </div>
        );
      })}
    </div>
  );
}
