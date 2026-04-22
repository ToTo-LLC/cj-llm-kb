import { redirect } from "next/navigation";

import { InboxScreen } from "@/components/inbox/inbox-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /inbox — ingest surface (server component).
 *
 * Mirrors the ``/chat`` and ``/pending`` pattern: read the per-run API
 * token on the server so it never round-trips through a browser fetch,
 * redirect to the setup wizard when the token is missing, then delegate
 * to the client ``<InboxScreen />`` which owns the list + drop zone
 * state.
 *
 * Plan 07 Task 17.
 */
export default async function InboxPage(): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  return <InboxScreen />;
}
