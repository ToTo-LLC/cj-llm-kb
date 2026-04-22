"use client";

// /settings — default route (Client Component, Plan 08 Task 2).
//
// Settings routing lives at ``/settings/<tab>/``. Plain ``/settings/`` has no
// dedicated landing page; redirect the caller to the General tab via the
// client router so the static export is still a valid static file.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SettingsPage(): React.ReactElement | null {
  const router = useRouter();
  useEffect(() => {
    router.replace("/settings/general/");
  }, [router]);
  return null;
}
