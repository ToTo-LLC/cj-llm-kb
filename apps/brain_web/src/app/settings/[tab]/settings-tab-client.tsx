"use client";

// /settings/<tab> client renderer — reads the active tab from the URL path
// (not ``useParams()``) for the same reason spelled out in
// ``chat-thread-client.tsx``: under static export, ``useParams()`` returns
// the build-time placeholder, not the live URL segment.

import { usePathname } from "next/navigation";

import { SettingsScreen } from "@/components/settings/settings-screen";

export function SettingsTabClient(): React.ReactElement {
  const pathname = usePathname();
  const match = pathname.match(/^\/settings\/([^/]+)\/?$/);
  const tab = match?.[1] ?? "general";
  return <SettingsScreen activeTab={tab} />;
}
