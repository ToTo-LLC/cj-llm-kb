"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { Wizard } from "@/components/setup/wizard";

/**
 * Full-screen setup wizard page. Client component — the wizard is fully
 * interactive and has no server-side dependencies.
 *
 * Plan 08 Task 2: first-run detection now lives in the bootstrap context,
 * which pushes the user to ``/setup/`` when no BRAIN.md + no token. On
 * completion we push to ``/chat/`` — trailing slash matches the static-
 * export URL form (``trailingSlash: true`` in next.config.mjs).
 *
 * The ``localStorage.brain-setup-done`` flag is purely a UX signal so we
 * don't fight the bootstrap redirect on the immediate post-wizard navigation
 * while the backend's on-disk state is settling.
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
    router.push("/chat/");
  }, [router]);

  return <Wizard onDone={handleDone} />;
}
