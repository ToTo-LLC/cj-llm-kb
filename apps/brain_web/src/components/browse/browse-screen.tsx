"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, GitCompare } from "lucide-react";

import {
  configGet,
  proposeNote,
  readNote,
  recent,
  type RecentEntry,
} from "@/lib/api/tools";
import { useAppStore } from "@/lib/state/app-store";
import { useBrowseStore } from "@/lib/state/browse-store";
import { useSystemStore } from "@/lib/state/system-store";
import { useDomains } from "@/lib/hooks/use-domains";
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
  /** Vault name — fed into the Obsidian URI. When omitted, the
   *  component falls back to ``brain_config_get("vault_path")`` and
   *  uses the basename of the returned path (so a vault at
   *  ``~/Documents/my-brain`` shows up as ``my-brain`` in the
   *  Obsidian deep-link). The prop override exists for tests and
   *  for any caller that already has the value cached. */
  vaultName?: string;
}

/** Module-level cache so the configGet round-trip happens at most once
 *  per session. The vault path is fixed for a given brain process — it
 *  cannot change without a restart — so caching is safe. */
let cachedVaultName: string | null = null;

function basename(p: string): string {
  // Cross-platform basename: split on both ``/`` and ``\``, keep the
  // last non-empty segment. Falls back to "brain" if the path is
  // empty/garbled.
  const trimmed = p.replace(/[\\/]+$/, ""); // drop trailing slashes
  const parts = trimmed.split(/[\\/]/);
  const last = parts[parts.length - 1] ?? "";
  return last || "brain";
}

/** Load the vault name from ``brain_config_get("vault_path")``. Returns
 *  the prop override immediately if supplied; otherwise resolves the
 *  config call once and caches the basename for subsequent renders.
 *  Falls back to ``"brain"`` on any error so the Obsidian deep-link
 *  always renders something. */
function useVaultName(override?: string): string {
  const [name, setName] = React.useState<string>(
    override ?? cachedVaultName ?? "brain",
  );

  React.useEffect(() => {
    if (override !== undefined) return; // caller has it; nothing to fetch
    if (cachedVaultName !== null) return; // session-cache hit

    let cancelled = false;
    configGet({ key: "vault_path" })
      .then((res) => {
        if (cancelled) return;
        const value =
          res.data && typeof res.data.value === "string"
            ? res.data.value
            : null;
        if (value) {
          cachedVaultName = basename(value);
          setName(cachedVaultName);
        }
      })
      .catch(() => {
        // Best-effort. If the config call fails the fallback "brain"
        // already on screen is correct for the default vault location.
      });
    return () => {
      cancelled = true;
    };
  }, [override]);

  return override ?? name;
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
  vaultName: vaultNameProp,
}: BrowseScreenProps): React.ReactElement {
  const router = useRouter();
  // Issue #14: vault name now flows from ``brain_config_get("vault_path")``
  // rather than the hardcoded prop default. The hook respects an explicit
  // prop override (used by tests + any caller that already has it cached).
  const vaultName = useVaultName(vaultNameProp);
  const scope = useAppStore((s) => s.scope);
  const pushToast = useSystemStore((s) => s.pushToast);
  const setBrowseCurrent = useBrowseStore((s) => s.setCurrent);

  const [notes, setNotes] = React.useState<FileTreeNote[]>([]);
  const [loading, setLoading] = React.useState(true);
  // Plan 10 Task 7: live domain list (cached singleton). Used as the
  // recent-notes bucket source AND passed to FileTree so empty
  // domains still render their header.
  const { domains: liveDomains } = useDomains();
  const liveDomainSlugs = React.useMemo(
    () => liveDomains.map((d) => d.slug),
    [liveDomains],
  );
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
  // Plan 10 Task 7: domain source flipped from a per-mount listDomains
  // call to the cached useDomains() hook so the topbar + browse share
  // one fetch.
  React.useEffect(() => {
    if (liveDomainSlugs.length === 0) return; // wait for hook hydration
    let cancelled = false;
    (async () => {
      try {
        const buckets = await Promise.all(
          liveDomainSlugs.map((d) =>
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
    // ``liveDomainSlugs`` is the only effect input we read; ``active``
    // and ``scope`` are read inside but only to seed the initial
    // selection, which we don't want to rerun on every scope change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveDomainSlugs]);

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
        domains={liveDomainSlugs}
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
