"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { Wizard } from "@/components/setup/wizard";

/**
 * Full-screen setup wizard page. Client component — the wizard is fully
 * interactive and has no server-side dependencies once the page is reached
 * (first-run detection happens upstream in `app/page.tsx`).
 *
 * `onDone` sets `localStorage.brain-setup-done=1` + routes to `/chat`. The
 * flag is a client-side signal only — the real first-run check lives in
 * `detectSetupStatus()` and uses on-disk state (vault / BRAIN.md / token),
 * which is the source of truth. The localStorage flag is purely a UX signal
 * so we don't re-trigger a redirect loop while SSR state is warming.
 */
export default function SetupPage() {
  const router = useRouter();

  const handleDone = useCallback(() => {
    try {
      window.localStorage.setItem("brain-setup-done", "1");
    } catch {
      // localStorage may be unavailable (private window on Safari is the
      // usual suspect). Not fatal — disk state is authoritative.
    }
    router.push("/chat");
  }, [router]);

  return <Wizard onDone={handleDone} />;
}
