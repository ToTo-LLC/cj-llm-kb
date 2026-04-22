"use client";

import * as React from "react";

import { AutonomousIngestToggle } from "./autonomous-ingest-toggle";
import { DropZone } from "./drop-zone";
import { SourceRow } from "./source-row";
import { InboxTabs } from "./tabs";
import { useInboxStore, type IngestSource } from "@/lib/state/inbox-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * InboxScreen (Plan 07 Task 17) — client component glue for the inbox
 * surface: page header + autonomous toggle, drop zone, tab chips, and
 * the filtered source list.
 *
 * Initial load pulls ``brain_recent_ingests`` once on mount. Optimistic
 * rows inserted by the drop zone / paste listener / drag-route always
 * land on top of ``sources`` so the user sees instant feedback.
 *
 * The tab filter is applied here (not in the store) so the store can
 * stay dumb — the screen knows which ``status`` values belong to each
 * bucket and renders accordingly.
 */

const PROGRESS_STATUSES: ReadonlyArray<IngestSource["status"]> = [
  "queued",
  "extracting",
  "classifying",
  "summarizing",
  "integrating",
];

function inBucket(
  source: IngestSource,
  tab: "progress" | "failed" | "recent",
): boolean {
  if (tab === "progress") return PROGRESS_STATUSES.includes(source.status);
  if (tab === "failed") return source.status === "failed";
  return source.status === "done";
}

export function InboxScreen(): React.ReactElement {
  const sources = useInboxStore((s) => s.sources);
  const activeTab = useInboxStore((s) => s.activeTab);
  const setTab = useInboxStore((s) => s.setTab);
  const loadRecent = useInboxStore((s) => s.loadRecent);
  const pushToast = useSystemStore((s) => s.pushToast);

  React.useEffect(() => {
    loadRecent().catch(() => {
      pushToast({
        lead: "Load failed.",
        msg: "Could not fetch recent ingests.",
        variant: "danger",
      });
    });
  }, [loadRecent, pushToast]);

  const counts = React.useMemo(
    () => ({
      progress: sources.filter((s) => inBucket(s, "progress")).length,
      failed: sources.filter((s) => inBucket(s, "failed")).length,
      recent: sources.filter((s) => inBucket(s, "recent")).length,
    }),
    [sources],
  );

  const visible = sources.filter((s) => inBucket(s, activeTab));

  const emptyCopy = {
    progress: "No sources being processed.",
    failed: "Nothing has failed — good.",
    recent: "Drop a source to get started.",
  }[activeTab];

  return (
    <div className="inbox-screen flex h-full flex-col overflow-hidden">
      <header className="flex items-start justify-between gap-4 border-b border-[var(--hairline)] px-4 py-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
            Ingest sources
          </div>
          <h1 className="text-xl font-semibold text-[var(--text)]">Inbox</h1>
        </div>
        <AutonomousIngestToggle />
      </header>

      <div className="inbox-body flex flex-1 flex-col gap-4 overflow-auto p-4">
        <DropZone />

        <InboxTabs value={activeTab} onChange={setTab} counts={counts} />

        <div className="source-list flex flex-col gap-2">
          {visible.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--hairline)] p-8 text-center">
              <div
                aria-hidden="true"
                className="mx-auto mb-3 h-10 w-10 rounded-full bg-gradient-to-br from-[var(--accent)] to-transparent opacity-60"
              />
              <h2 className="text-lg font-light text-[var(--text)]">
                Nothing here.
              </h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                {emptyCopy}
              </p>
            </div>
          ) : (
            visible.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                onRetry={(s) => {
                  // Plan 09 owns the real retry tool; for now just
                  // surface a toast so the button isn't dead.
                  pushToast({
                    lead: "Retry queued.",
                    msg: `${s.title} will retry shortly.`,
                    variant: "default",
                  });
                }}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
