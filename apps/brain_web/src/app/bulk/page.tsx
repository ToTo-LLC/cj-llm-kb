import { redirect } from "next/navigation";

import { BulkScreen } from "@/components/bulk/bulk-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /bulk — bulk-import surface (server component).
 *
 * Mirrors the ``/chat`` / ``/pending`` / ``/inbox`` pattern: read the
 * per-run API token on the server so it never round-trips through the
 * browser, redirect to the setup wizard when the token is missing, then
 * delegate to the client ``<BulkScreen />`` which owns the 4-step flow.
 *
 * Plan 07 Task 21.
 */
export default async function BulkPage(): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  return <BulkScreen />;
}
