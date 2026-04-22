// /settings/<tab> — Server Component shell for static export (Plan 08 Task 2).
//
// Pre-render the five known tabs so their HTML lands in the static bundle.
// Unknown tabs fall through to the SPA fallback on the backend — the client
// screen itself replaces unknown tab values with ``general``.

import { SettingsTabClient } from "./settings-tab-client";

// Pre-render the six known tabs so their HTML lands in the static bundle.
// ``dynamicParams`` defaults to ``false`` under static export, meaning
// unknown tab values 404 at the Next.js layer — brain_api's SPA fallback
// then serves ``index.html`` and the client-side ``<SettingsScreen />``
// normalises the active tab to ``general``.
export async function generateStaticParams(): Promise<{ tab: string }[]> {
  return [
    { tab: "general" },
    { tab: "domains" },
    { tab: "providers" },
    { tab: "autonomous" },
    { tab: "integrations" },
    { tab: "backups" },
  ];
}

export default function SettingsTabPage(): React.ReactElement {
  return <SettingsTabClient />;
}
