import { redirect } from "next/navigation";

import { PendingScreen } from "@/components/pending/pending-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /pending — approval queue route (server component).
 *
 * Mirrors the ``/chat`` page pattern: read the per-run API token on
 * the server so it never round-trips through a browser fetch, redirect
 * to the setup wizard when the token is missing, then delegate to the
 * client ``<PendingScreen />`` which owns the list + detail state.
 *
 * Plan 07 Task 16.
 */
export default async function PendingPage(): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  return <PendingScreen />;
}
