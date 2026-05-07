"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, GitCompare } from "lucide-react";

import { AUTONOMY_CATEGORIES, configGet } from "@/lib/api/tools";
import {
  usePendingStore,
  type PatchEnvelope,
} from "@/lib/state/pending-store";
import {
  type AutonomyDomainFlags,
  useSettingsStore,
} from "@/lib/state/settings-store";
import { cn } from "@/lib/utils";

import { PatchCard, type PatchCardPatch } from "./patch-card";

/**
 * PendingRail (Plan 07 Task 16) — compact right-rail variant of the
 * pending list used on the ``/chat`` route.
 *
 * Same PatchCard primitive as the full screen, but:
 *   - No inline action buttons (``inRail`` hides them — the full screen
 *     is where approvals happen).
 *   - An "Autonomous on" banner sits above the list when any
 *     ``autonomous.*`` flag is enabled (fetched once on mount).
 *   - A small "Open full view →" link to ``/pending`` so the user can
 *     transition without losing context.
 *
 * The rail ALSO listens for the ``brain:review-patch`` custom event
 * dispatched by the ``<InlinePatchCard />`` "Review in panel →" button
 * (see Task 14). On event it scrolls the matching card into view and
 * paints a brief highlight pulse. Keeping the coupling event-based
 * means InlinePatchCard can sit in any part of the chat transcript
 * without threading a callback through.
 */

function envelopeToCardPatch(envelope: PatchEnvelope): PatchCardPatch {
  const domain =
    typeof envelope.domain === "string"
      ? envelope.domain
      : envelope.target_path.split("/")[0] ?? "research";
  return {
    patch_id: envelope.patch_id,
    tool: (envelope.tool as string) ?? "propose_note",
    domain,
    target_path: envelope.target_path,
    reason: envelope.reason,
    created_at: envelope.created_at,
    isNew: envelope.isNew === true,
  };
}

export function PendingRail(): React.ReactElement {
  const patches = usePendingStore((s) => s.patches);
  const loadPending = usePendingStore((s) => s.loadPending);
  const hydrateAutonomous = useSettingsStore((s) => s.hydrateAutonomous);
  // Plan 16 T40 fix-up: derive from the per-domain settings-store map.
  // Banner shows iff ANY domain has ANY of the 5 category flags set true.
  // Pre-T40 read 5 flat ``autonomous.<flag>`` keys via configGet, but
  // T38 reshaped Config.autonomous to dict[str, AutonomyCategoryFlags];
  // those flat keys no longer resolve and silently failed.
  const autonomousOn = useSettingsStore((s) =>
    Object.values(s.autonomous).some((flags) =>
      Object.values(flags).some((v) => v === true),
    ),
  );
  const [highlightId, setHighlightId] = React.useState<string | null>(null);

  // Load pending on mount so the rail shows a warm list.
  React.useEffect(() => {
    loadPending().catch(() => {
      // Silent: the rail is a read-only surface; failures show up on the
      // full pending screen with a proper toast.
    });
  }, [loadPending]);

  // Mount-time hydrate of the autonomous snapshot from the backend so
  // the banner is correct even when the user hasn't visited the
  // Settings → Autonomy panel this session. One ``configGet({key:"autonomous"})``
  // call returns the full per-domain × per-category dict; same shape as
  // ``readAutonomousSnapshot`` in panel-autonomous.tsx.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await configGet({ key: "autonomous" });
        const raw = (res.data as { value?: unknown } | null)?.value;
        if (cancelled || !raw || typeof raw !== "object" || Array.isArray(raw)) {
          return;
        }
        const snapshot: Record<string, AutonomyDomainFlags> = {};
        for (const [slug, rawFlags] of Object.entries(raw as Record<string, unknown>)) {
          if (!rawFlags || typeof rawFlags !== "object") continue;
          const flags: AutonomyDomainFlags = {};
          for (const cat of AUTONOMY_CATEGORIES) {
            const val = (rawFlags as Record<string, unknown>)[cat];
            if (typeof val === "boolean") flags[cat] = val;
          }
          snapshot[slug] = flags;
        }
        if (!cancelled) hydrateAutonomous(snapshot);
      } catch {
        // Silent — config-get failures shouldn't crash the rail.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hydrateAutonomous]);

  // Listen for inline-patch-card's "Review in panel →" event. Scroll
  // the matching card into view and flash a highlight.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (ev: Event) => {
      const detail = (ev as CustomEvent).detail as { patchId?: string };
      const id = detail?.patchId;
      if (!id) return;
      setHighlightId(id);
      const el = document.getElementById(`rail-patch-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      // Clear the highlight after a beat so the pulse animation can replay
      // the next time the user reviews a different patch.
      window.setTimeout(() => setHighlightId(null), 1500);
    };
    window.addEventListener("brain:review-patch", handler);
    return () => window.removeEventListener("brain:review-patch", handler);
  }, []);

  return (
    <div className="flex h-full flex-col gap-2 p-3">
      <div className="flex items-center gap-2">
        <GitCompare className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
          Pending
        </span>
        <span className="text-[11px] text-[var(--text-dim)]">
          · {patches.length}
        </span>
        <Link
          href="/pending"
          className="ml-auto text-[11px] text-[var(--accent)] hover:underline"
        >
          Open pending →
        </Link>
      </div>

      {autonomousOn && (
        <div
          className={cn(
            "flex items-start gap-2 rounded-md border border-amber-400/40",
            "bg-amber-950/30 px-2 py-1.5 text-[11px] text-amber-300",
          )}
          role="status"
        >
          <AlertTriangle className="mt-0.5 h-3 w-3" />
          <div>
            <strong>Autonomous mode is on.</strong>{" "}
            Some categories apply without review.
          </div>
        </div>
      )}

      {patches.length === 0 ? (
        <div className="mt-6 rounded-md border border-dashed border-[var(--hairline)] p-4 text-center text-xs text-[var(--text-dim)]">
          All clear.
          <div className="mt-1">
            Ingest a source or start a chat to stage new changes.
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 overflow-auto">
          {patches.map((envelope) => (
            <div
              key={envelope.patch_id}
              id={`rail-patch-${envelope.patch_id}`}
              className={cn(
                highlightId === envelope.patch_id &&
                  "ring-2 ring-[var(--accent)] rounded-md",
              )}
            >
              <PatchCard
                patch={envelopeToCardPatch(envelope)}
                selected={false}
                inRail
                onSelect={() => {}}
                onApprove={() => {}}
                onEdit={() => {}}
                onReject={() => {}}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
