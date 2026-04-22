"use client";

// /pending — approval queue route (Client Component, Plan 08 Task 2).
//
// Client-component port of the old server-gated page. ``<BootstrapProvider>``
// in the layout has already redirected first-run users to /setup/ by the
// time this renders, so the PendingScreen's API calls will have a token
// available via ``useTokenStore``. No token prop threading is needed because
// every tool binding reads ``getToken()`` lazily.

import { PendingScreen } from "@/components/pending/pending-screen";

export default function PendingPage(): React.ReactElement {
  return <PendingScreen />;
}
