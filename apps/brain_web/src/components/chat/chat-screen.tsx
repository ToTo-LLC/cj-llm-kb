"use client";

import * as React from "react";

import { ChatSubHeader } from "./chat-sub-header";
import { Composer } from "./composer";
import { Transcript } from "./transcript";
import {
  CrossDomainModal,
  computeRailedSlugsInScope,
  shouldFireCrossDomainModal,
} from "@/components/dialogs/cross-domain-modal";
import { DocPanel } from "@/components/draft/doc-panel";
import { setCrossDomainWarningAcknowledged } from "@/lib/api/tools";
import { useCrossDomainGate } from "@/lib/hooks/use-cross-domain-gate";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDraftStore } from "@/lib/state/draft-store";
import { useSystemStore } from "@/lib/state/system-store";
import { useChatWebSocket } from "@/lib/ws/hooks";

/**
 * ChatScreen (Plan 07 Task 15).
 *
 * Composition root for the /chat and /chat/<thread_id> routes. Owns the
 * per-thread WS lifecycle via ``useChatWebSocket`` and wires the
 * Composer's send/cancel/detach events back to the hook's typed send
 * methods.
 *
 * Active thread → ``threadId`` is non-null, WS opens, transcript
 *   hydrates via ``thread_loaded`` + replay events.
 * New thread → ``threadId === null``, WS stays closed, Transcript
 *   renders NewThreadEmpty until the backend creates the thread.
 *
 * The ``token`` prop is read by the server-component wrapper around the
 * chat route (``app/chat/page.tsx`` / ``app/chat/[thread_id]/page.tsx``)
 * from the per-run API token file. Null token → hook stays inert, so
 * the screen is safe to mount before setup completes.
 */

export interface ChatScreenProps {
  /** Active thread id or ``null`` for the new-thread route. */
  threadId: string | null;
  /** Per-run API token from ``.brain/run/api-secret.txt``. */
  token: string | null;
}

export function ChatScreen({
  threadId,
  token,
}: ChatScreenProps): React.ReactElement {
  const setActiveThreadId = useAppStore((s) => s.setActiveThreadId);
  const clearTranscript = useChatStore((s) => s.clearTranscript);
  const mode = useAppStore((s) => s.mode);
  const scope = useAppStore((s) => s.scope);
  const pendingAttachedSources = useChatStore(
    (s) => s.pendingAttachedSources,
  );
  const removeAttachedSource = useChatStore((s) => s.removeAttachedSource);
  const pushToast = useSystemStore((s) => s.pushToast);

  const activeDoc = useDraftStore((s) => s.activeDoc);
  const showDocPanel = mode === "draft" && activeDoc !== null;

  const { sendTurnStart, cancelTurn } = useChatWebSocket(threadId, token);

  // Plan 12 Task 9 — cross-domain confirmation modal trigger gate.
  //
  // The "session" being finalized is the new thread that the FIRST
  // send creates; once ``threadId`` is non-null the user has already
  // implicitly accepted the scope for this thread (re-asking on every
  // turn would be hostile). The trigger compares the current scope
  // against ``Config.privacy_railed`` AND respects the
  // ``cross_domain_warning_acknowledged`` opt-out — see
  // ``shouldFireCrossDomainModal`` for the full predicate.
  //
  // ``pendingSendRef`` parks the user's first message + send options
  // while the modal is open. On Continue we replay; on Back-to-scope
  // we drop. Using a ref (not state) avoids a render cycle between
  // "open modal" and "remember the message" — the values are captured
  // at click time, not at render time.
  const {
    privacyRailed,
    acknowledged,
    loading: gateLoading,
    refresh: refreshGate,
  } = useCrossDomainGate();
  const [crossDomainModalOpen, setCrossDomainModalOpen] = React.useState(false);
  const pendingSendRef = React.useRef<{
    text: string;
    attachedSources: string[] | undefined;
    mode: typeof mode;
  } | null>(null);

  // Keep the URL-derived active-thread-id in sync with app-store so the
  // topbar / rail can react without digging into Next.js params. Clear
  // transcript on thread-id change to avoid bleeding state across threads.
  React.useEffect(() => {
    setActiveThreadId(threadId);
    clearTranscript();
    return () => {
      setActiveThreadId(null);
    };
  }, [threadId, setActiveThreadId, clearTranscript]);

  // Task 20 will feed real thread metadata (turn count, cost) from the
  // threads API. For now show the new-thread variant when no id is
  // present — the active-thread title hydrates off ``turn_end``'s
  // ``title`` field via Task 20's wiring.
  const subHeaderThread = threadId
    ? { title: "untitled thread", turns: 0, cost: 0 }
    : null;

  const dispatchSend = React.useCallback(
    (text: string, attachedSources: string[] | undefined) => {
      sendTurnStart(text, {
        mode,
        attachedSources,
      });
    },
    [sendTurnStart, mode],
  );

  const handleSend = React.useCallback(
    (text: string) => {
      const attachedSources =
        pendingAttachedSources.length > 0
          ? pendingAttachedSources
          : undefined;

      // Trigger gate only fires for new-thread sends. After the first
      // turn the thread exists; ``threadId`` flips non-null and we
      // never re-prompt for the same conversation. ``gateLoading``
      // means we haven't finished hydrating ``Config`` yet — fire
      // the send through unchanged so a slow first-mount doesn't
      // make the composer appear broken; the user can re-trigger
      // the next turn if needed (rare race).
      if (
        threadId === null &&
        !gateLoading &&
        shouldFireCrossDomainModal(scope, privacyRailed, acknowledged)
      ) {
        pendingSendRef.current = {
          text,
          attachedSources,
          mode,
        };
        setCrossDomainModalOpen(true);
        return;
      }

      dispatchSend(text, attachedSources);
    },
    [
      threadId,
      gateLoading,
      scope,
      privacyRailed,
      acknowledged,
      mode,
      pendingAttachedSources,
      dispatchSend,
    ],
  );

  const handleCrossDomainContinue = React.useCallback(
    async (alsoAcknowledge: boolean) => {
      const pending = pendingSendRef.current;
      pendingSendRef.current = null;
      setCrossDomainModalOpen(false);

      // Persist the acknowledgment FIRST so a slow ack-write can't
      // race a fast WS turn that would re-fire the modal next time.
      // The send dispatches once the persistence resolves OR we know
      // the user opted out of acknowledging (in which case the modal
      // will simply fire again on the next new-thread send).
      if (alsoAcknowledge) {
        try {
          await setCrossDomainWarningAcknowledged(true);
          // Plan 13 Task 3: ``refreshGate()`` now delegates to the
          // ``useCrossDomainGateStore`` zustand store so every peer
          // consumer (the Settings toggle in panel-domains.tsx, any
          // future cross-instance subscriber) re-renders with the
          // new value automatically. Without the store promotion the
          // toggle would have stayed stale until the user reloaded
          // the Settings panel.
          await refreshGate();
        } catch {
          // Match the toast-on-failure pattern from Task 7's
          // out-of-scope notes. Surface a non-blocking warning; the
          // send still proceeds because the user already clicked
          // Continue.
          pushToast({
            lead: "Couldn't save.",
            msg:
              "The cross-domain setting didn't save. The check will run again next time.",
            variant: "danger",
          });
        }
      }

      if (pending !== null) {
        dispatchSend(pending.text, pending.attachedSources);
      }
    },
    [dispatchSend, refreshGate, pushToast],
  );

  const handleCrossDomainCancel = React.useCallback(() => {
    pendingSendRef.current = null;
    setCrossDomainModalOpen(false);
  }, []);

  const railedSlugsInScope = React.useMemo(
    () => computeRailedSlugsInScope(scope, privacyRailed),
    [scope, privacyRailed],
  );

  const chatColumn = (
    <div className="flex h-full flex-col">
      <ChatSubHeader thread={subHeaderThread} />
      <div className="flex-1 overflow-hidden">
        <Transcript />
      </div>
      <Composer
        onSend={handleSend}
        onCancel={cancelTurn}
        onDetach={removeAttachedSource}
      />
    </div>
  );

  // Plan 12 Task 9 — modal lives at the screen-level so it portals
  // outside the column layout (Radix handles the portal). Mounting
  // inside ``chatColumn`` would still work but reads worse next to
  // the column's flex layout.
  const crossDomainOverlay = (
    <CrossDomainModal
      open={crossDomainModalOpen}
      scope={scope}
      railedSlugsInScope={railedSlugsInScope}
      onContinue={(ack) => void handleCrossDomainContinue(ack)}
      onCancel={handleCrossDomainCancel}
    />
  );

  if (showDocPanel) {
    return (
      <>
        <main
          className="grid h-full"
          style={{ gridTemplateColumns: "1fr 420px" }}
        >
          {chatColumn}
          <DocPanel />
        </main>
        {crossDomainOverlay}
      </>
    );
  }

  return (
    <>
      <main className="h-full">{chatColumn}</main>
      {crossDomainOverlay}
    </>
  );
}
