import { redirect } from "next/navigation";

import { SettingsScreen } from "@/components/settings/settings-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /settings/<tab> — active settings panel route (server component).
 *
 * Mirrors the ``/chat`` / ``/inbox`` / ``/pending`` pattern: reads the
 * per-run API token on the server (never crosses the browser fetch),
 * redirects to setup when missing, then delegates to the client
 * ``<SettingsScreen />`` which owns tab-state + panel rendering.
 *
 * Next.js 15 passes ``params`` as a Promise to server components —
 * awaiting unwraps the ``tab`` segment. Unknown tabs are handled inside
 * ``<SettingsScreen />`` (which replaces the URL with ``/settings/general``).
 */

type Params = { tab: string };

interface SettingsTabPageProps {
  params: Promise<Params>;
}

export default async function SettingsTabPage({
  params,
}: SettingsTabPageProps): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  const { tab } = await params;
  return <SettingsScreen activeTab={tab} />;
}
