"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { listThreads, type ChatThreadEntry } from "@/lib/api/tools";

/**
 * RecentThreads (issue #18) — left-nav recent-chats panel.
 *
 * Fetches via ``brain_list_threads`` once on mount, then groups the
 * results by relative date (Today / Yesterday / This week / Earlier)
 * matching the v4 mockup's ``nav-threads`` block. Falls back silently
 * to a hidden state on fetch error so the rest of the nav still
 * renders — the threads panel is a "nice to have" that should never
 * gate left-nav usability.
 *
 * Class names match ``brand-skin.css`` selectors (``.nav-thread``,
 * ``.nav-thread-date``, ``.t-title``, ``.t-meta``, ``.mode-chip``)
 * so the brand styling cascades.
 */

type Bucket = "Today" | "Yesterday" | "This week" | "Earlier";

const BUCKET_ORDER: readonly Bucket[] = [
  "Today",
  "Yesterday",
  "This week",
  "Earlier",
];

function bucketFor(updatedAt: string, now: Date = new Date()): Bucket {
  const t = Date.parse(updatedAt);
  if (Number.isNaN(t)) return "Earlier";
  const updated = new Date(t);
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOfThisWeek = new Date(startOfToday);
  startOfThisWeek.setDate(startOfThisWeek.getDate() - 7);

  if (updated >= startOfToday) return "Today";
  if (updated >= startOfYesterday) return "Yesterday";
  if (updated >= startOfThisWeek) return "This week";
  return "Earlier";
}

function titleFor(thread: ChatThreadEntry): string {
  // Title isn't stored separately yet — derive from the thread_id
  // basename. A future plan can land a chat_threads.title column and
  // the chat session can populate it from the first user message.
  // For now: ``research/chats/fisher-ury.md`` → ``fisher-ury``.
  const slug =
    thread.path
      .split("/")
      .pop()
      ?.replace(/\.md$/, "") ?? thread.thread_id;
  return slug;
}

function relativeAge(updatedAt: string, now: Date = new Date()): string {
  const t = Date.parse(updatedAt);
  if (Number.isNaN(t)) return "";
  const ms = now.getTime() - t;
  const minutes = Math.round(ms / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.round(days / 7);
  return `${weeks}w ago`;
}

export function RecentThreads(): React.ReactElement {
  const pathname = usePathname();
  const [threads, setThreads] = React.useState<ChatThreadEntry[]>([]);
  const [loaded, setLoaded] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    listThreads({ limit: 30 })
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.threads ?? [];
        setThreads(list);
        setLoaded(true);
      })
      .catch(() => {
        // Silent fallback — the static nav above is still usable.
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Group once per render; threads are usually small (~30) so this is
  // cheap. The Map iteration order matches BUCKET_ORDER below.
  const grouped = React.useMemo<Record<Bucket, ChatThreadEntry[]>>(() => {
    const out: Record<Bucket, ChatThreadEntry[]> = {
      Today: [],
      Yesterday: [],
      "This week": [],
      Earlier: [],
    };
    for (const t of threads) {
      out[bucketFor(t.updated_at)].push(t);
    }
    return out;
  }, [threads]);

  if (!loaded || threads.length === 0) {
    // Render nothing rather than a spinner / empty state — the panel is
    // optional and a brand-new vault has no threads. The user discovers
    // it once they actually start a chat.
    return <></>;
  }

  return (
    <div className="nav-threads flex flex-col gap-1">
      <div className="nav-section mt-3 px-3 text-[10px] uppercase tracking-wider">
        Threads
      </div>
      {BUCKET_ORDER.map((bucket) => {
        const items = grouped[bucket];
        if (items.length === 0) return null;
        return (
          <React.Fragment key={bucket}>
            <div className="nav-thread-date px-3 pt-1 text-[10px] uppercase tracking-wider">
              {bucket}
            </div>
            {items.map((t) => {
              const href = `/chat/${encodeURIComponent(t.thread_id)}`;
              const active = pathname?.startsWith(href);
              return (
                <Link
                  key={t.thread_id}
                  href={href}
                  className={`nav-thread block px-3 py-1.5 text-sm ${active ? "active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <div className="t-title truncate">{titleFor(t)}</div>
                  <div className="t-meta flex items-center gap-2 text-[11px]">
                    <span className="mode-chip uppercase">{t.mode}</span>
                    <span
                      aria-hidden="true"
                      className="dot inline-block h-[5px] w-[5px] rounded-full"
                      style={{ background: `var(--dom-${t.domain})` }}
                    />
                    <span>{relativeAge(t.updated_at)}</span>
                  </div>
                </Link>
              );
            })}
          </React.Fragment>
        );
      })}
    </div>
  );
}
