"use client";

// Root route — Client Component under static export (Plan 08 Task 2).
//
// This component runs in two paths:
//
// 1. First load is literally ``/`` → we router.replace() to /setup/ or /chat/
//    based on the bootstrap state. This is the "welcome you to the right
//    place" behaviour that replaced the old server-side redirect.
//
// 2. brain_api's SPA fallback served this page's ``index.html`` for a
//    deeper URL (e.g. ``/chat/abc123/``). In that case we MUST NOT replace
//    the URL — the Next.js client router will hydrate whichever route the
//    browser pathname actually points at, not the root. The early return on
//    "pathname isn't root" preserves the URL so deep links keep working.
//
// Returning ``null`` in both paths is fine: path (1) never renders visible
// content (the ``router.replace`` fires before the "Starting brain…" BootGate
// placeholder resolves), and path (2) never runs to completion because Next
// mounts a different route component as soon as hydration stabilises the URL.
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useBootstrap } from "@/lib/bootstrap/bootstrap-context";

export default function RootPage(): React.ReactElement | null {
  const router = useRouter();
  const pathname = usePathname();
  const { loading, isFirstRun, error } = useBootstrap();

  useEffect(() => {
    if (loading || error) return;
    // Only run the "root landing" redirect when the user actually asked for
    // the root. For anything else (SPA fallback serving this page's HTML on
    // a deep URL), the client router re-mounts the correct page — don't
    // rewrite the URL out from under it.
    if (pathname !== "/") return;
    if (isFirstRun) {
      router.replace("/setup/");
    } else {
      router.replace("/chat/");
    }
  }, [loading, error, isFirstRun, pathname, router]);

  return null;
}
