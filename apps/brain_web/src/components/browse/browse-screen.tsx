"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, GitCompare } from "lucide-react";

import {
  listDomains,
  proposeNote,
  readNote,
  recent,
  type RecentEntry,
} from "@/lib/api/tools";
import { useAppStore } from "@/lib/state/app-store";
import { useBrowseStore } from "@/lib/state/browse-store";
import { useSystemStore } from "@/lib/state/system-store";
import { resolveLink } from "@/lib/vault/wikilinks";

import { FileTree, type FileTreeNote } from "./file-tree";
import { MetaStrip } from "./meta-strip";
import { Reader } from "./reader";
import { VaultEditor } from "./monaco-editor";
import { WikilinkHover } from "./wikilink-hover";

/**
 * BrowseScreen (Plan 07 Task 18).
 *
 * Client owner of the browse view. Pulls the tree from
 * ``recent({limit: 200})`` as a stand-in for a future
 * ``brain_list_notes`` tool (Task 25 sweep), resolves the active
 * note via ``readNote``, and orchestrates:
 *
 *   - FileTree navigation
 *   - Reader ↔ VaultEditor toggle (save stages a patch via
 *     ``proposeNote``)
 *   - WikilinkHover (150 ms debounce + resolved-path lookup)
 *   - SearchOverlay (⌘K) — the global keydown handler lives at the
 *     AppShell level; we expose a simple ``openSearch`` callback
 *     for the FileTree's pseudo-button.
 */

export interface BrowseScreenProps {
  /** Optional pre-selected note path from ``/browse/[...path]``. */
  activePath?: string;
  /** Vault name — fed into Obsidian URI. For now taken from a
   *  prop; Task 25 sweep pipes the real value through
   *  ``brain_config_get("vault_name")``. */
  vaultName?: string;
}

function slugOf(path: string): string {
  return path.split("/").pop()?.replace(/\.md$/, "") ?? path;
}

function folderOf(path: string): string {
  const parts = path.split("/");
  return parts.length >= 3 ? parts[parts.length - 2] : "notes";
}

function domainOf(path: string): string {
  return path.split("/")[0] ?? "research";
}

function readTime(body: string): number {
  const words = body.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

export function BrowseScreen({
  activePath,
  vaultName = "brain",
}: BrowseScreenProps): React.ReactElement {
  const router = useRouter();
  const scope = useAppStore((s) => s.scope);
  const pushToast = useSystemStore((s) => s.pushToast);
  const setBrowseCurrent = useBrowseStore((s) => s.setCurrent);

  const [notes, setNotes] = React.useState<FileTreeNote[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [active, setActive] = React.useState<string | null>(
    activePath ?? null,
  );
  const [note, setNote] = React.useState<{
    title: string;
    body: string;
    frontmatter: Record<string, unknown>;
    modifiedAt: string;
  } | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [editBuf, setEditBuf] = React.useState("");
  const setSearchOpen = useSystemStore((s) => s.setSearchOpen);
  const [hover, setHover] = React.useState<{
    label: string;
    anchor: HTMLAnchorElement | null;
    timerId: number | null;
  }>({
    label: "",
    anchor: null,
    timerId: null,
  });

  // Build the tree from recent notes across every allowed domain.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const domainsRes = await listDomains();
        const domains = domainsRes.data?.domains ?? ["research", "work"];
        const buckets = await Promise.all(
          domains.map((d) =>
            recent({ domain: d, limit: 200 })
              .then((r) => ({ domain: d, items: r.data?.items ?? [] }))
              .catch(() => ({
                domain: d,
                items: [] as RecentEntry[],
              })),
          ),
        );
        if (cancelled) return;
        const flat: FileTreeNote[] = [];
        for (const bucket of buckets) {
          for (const item of bucket.items) {
            flat.push({
              path: item.path,
              title: slugOf(item.path),
              domain: item.domain ?? bucket.domain,
              folder: folderOf(item.path),
            });
          }
        }
        setNotes(flat);
        if (!active && flat.length > 0) {
          const first = flat.find((n) => scope.includes(n.domain)) ?? flat[0];
          setActive(first.path);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync active → reader body.
  React.useEffect(() => {
    if (!active) return;
    let cancelled = false;
    readNote({ path: active })
      .then((res) => {
        if (cancelled) return;
        const body = res.data?.body ?? "";
        const fm = res.data?.frontmatter ?? {};
        const title =
          typeof fm.title === "string" ? fm.title : slugOf(active);
        const modifiedAt =
          typeof fm.modified === "string" ? fm.modified : new Date().toISOString();
        setNote({ title, body, frontmatter: fm, modifiedAt });
        setEditBuf(body);
        setEditing(false);
      })
      .catch(() => {
        if (cancelled) return;
        setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [active]);

  // Stable slug index for wikilink resolution.
  const slugIndex = React.useMemo(() => {
    const idx: Record<string, string> = {};
    for (const n of notes) idx[slugOf(n.path)] = n.path;
    return idx;
  }, [notes]);

  // Publish active note + body into the browse-store so the
  // RightRail's ``<LinkedRail />`` can render backlinks + outlinks
  // without a cross-tree callback.
  React.useEffect(() => {
    setBrowseCurrent(active, note?.body ?? "", slugIndex);
  }, [active, note, slugIndex, setBrowseCurrent]);

  const handleWikilinkEnter = React.useCallback(
    (label: string, anchor: HTMLAnchorElement) => {
      if (hover.timerId) window.clearTimeout(hover.timerId);
      const timerId = window.setTimeout(() => {
        setHover({ label, anchor, timerId: null });
      }, 150);
      setHover((h) => ({ ...h, timerId }));
    },
    [hover.timerId],
  );

  const handleWikilinkLeave = React.useCallback(() => {
    if (hover.timerId) window.clearTimeout(hover.timerId);
    const timerId = window.setTimeout(() => {
      setHover({ label: "", anchor: null, timerId: null });
    }, 150);
    setHover((h) => ({ ...h, timerId }));
  }, [hover.timerId]);

  const saveEdit = async () => {
    if (!active) return;
    try {
      await proposeNote({
        path: active,
        content: editBuf,
        reason: "Direct edit from Browse",
      });
      pushToast({
        lead: "Saved as patch.",
        msg: "Queued in Pending for your review.",
        variant: "success",
        icon: "diff",
      });
      setEditing(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed.";
      pushToast({
        lead: "Save failed.",
        msg: message,
        variant: "danger",
      });
    }
  };

  const hoverPath = hover.label ? resolveLink(hover.label, slugIndex) : null;

  // Empty-state: nothing to browse.
  if (!loading && notes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--text-dim)]">
        No notes yet. Drop a source in the inbox to get started.
      </div>
    );
  }

  return (
    <div className="browse-screen grid h-full grid-cols-[260px_minmax(0,1fr)] overflow-hidden">
      <FileTree
        notes={notes}
        scope={scope}
        activePath={active}
        onOpenSearch={() => setSearchOpen(true)}
      />
      <div className="flex flex-col overflow-hidden">
        {note && active ? (
          <>
            <MetaStrip
              domain={domainOf(active)}
              folder={folderOf(active)}
              readTimeMin={readTime(note.body)}
              modifiedAt={note.modifiedAt}
              path={active}
              vaultName={vaultName}
              editing={editing}
              onToggleEdit={() => setEditing((e) => !e)}
            />
            <div className="relative flex flex-1 flex-col overflow-y-auto">
              {editing ? (
                <div className="editor-shell flex flex-1 flex-col">
                  <div className="editor-warn flex items-center gap-2 border-b border-[var(--hairline)] bg-[var(--surface-2)] px-4 py-2 text-xs text-[var(--text-muted)]">
                    <AlertTriangle size={12} />
                    <span>
                      You&apos;re editing the vault directly. Save will stage
                      a patch for review — no LLM in the loop.
                    </span>
                  </div>
                  <div className="flex-1">
                    <VaultEditor value={editBuf} onChange={setEditBuf} />
                  </div>
                  <div className="editor-actions flex items-center gap-2 border-t border-[var(--hairline)] bg-[var(--surface-2)] px-4 py-2 text-xs">
                    <span className="muted flex-1 text-[var(--text-dim)]">
                      {editBuf.split("\n").length} lines · {editBuf.length}{" "}
                      chars
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setEditBuf(note.body);
                      }}
                      className="rounded border border-[var(--hairline)] px-3 py-1 hover:bg-[var(--surface-3)]"
                    >
                      Discard
                    </button>
                    <button
                      type="button"
                      onClick={saveEdit}
                      className="inline-flex items-center gap-1 rounded bg-[var(--tt-cyan)] px-3 py-1 text-[var(--tt-ink)] hover:opacity-90"
                    >
                      <GitCompare size={12} />
                      Save as patch
                    </button>
                  </div>
                </div>
              ) : (
                <Reader
                  title={note.title}
                  frontmatter={note.frontmatter}
                  body={note.body}
                  onWikilinkEnter={handleWikilinkEnter}
                  onWikilinkLeave={handleWikilinkLeave}
                />
              )}
              {hoverPath && (
                <WikilinkHover
                  path={hoverPath}
                  anchor={hover.anchor}
                  onOpen={(p) => {
                    router.push(`/browse/${p}`);
                    setHover({ label: "", anchor: null, timerId: null });
                  }}
                />
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-dim)]">
            {loading ? "Loading…" : "Select a note to read."}
          </div>
        )}
      </div>
    </div>
  );
}
