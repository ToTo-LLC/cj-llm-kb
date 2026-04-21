// Root route — Server Component. Runs per SSR render (no cache in Task 13
// per Checkpoint 3 decision (3); Plan 09 revisits). Hits the filesystem to
// check for a vault + BRAIN.md + valid token, then redirects:
//
//   first-run  → /setup
//   otherwise  → /chat
//
// `redirect()` throws a Next.js internal exception, so this function never
// returns a React element — hence the `never` return type via async.
import { redirect } from "next/navigation";

import { detectSetupStatus } from "@/lib/setup/detect";

export default async function RootPage() {
  const status = await detectSetupStatus();
  if (status.isFirstRun) {
    redirect("/setup");
  }
  redirect("/chat");
}
