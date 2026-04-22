"use client";

// /inbox — ingest surface (Client Component, Plan 08 Task 2).
//
// Client-component port of the old server-gated page. First-run redirect
// happens upstream in ``<BootstrapProvider>``; the token is available via
// ``useTokenStore`` for every tool binding this screen calls.

import { InboxScreen } from "@/components/inbox/inbox-screen";

export default function InboxPage(): React.ReactElement {
  return <InboxScreen />;
}
