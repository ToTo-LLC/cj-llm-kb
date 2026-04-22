"use client";

// /browse/<...path> client renderer — reads the catch-all path from
// ``usePathname()`` (not ``useParams()``) so static-export deep URLs
// resolve to the right vault path. See ``chat-thread-client.tsx`` for the
// longer explanation of why ``useParams()`` returns the build-time
// placeholder under ``output: "export"``.

import { usePathname } from "next/navigation";

import { BrowseScreen } from "@/components/browse/browse-screen";

export function BrowsePathClient(): React.ReactElement {
  const pathname = usePathname();
  // ``/browse/<...>/`` — everything after ``/browse/`` is the vault-relative
  // path, minus the trailing slash. Empty or placeholder (``_``) means "no
  // specific note"; the screen then falls back to its default landing.
  const match = pathname.match(/^\/browse\/(.+?)\/?$/);
  const raw = match?.[1] ?? "";
  const joined = raw === "_" ? "" : raw;
  return <BrowseScreen activePath={joined || undefined} />;
}
