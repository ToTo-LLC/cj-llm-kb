// /browse/<...path> — Server Component shell (Plan 08 Task 2).
//
// Static export requires ``generateStaticParams()`` on dynamic segments; it
// can only be exported from a Server Component. We return an empty array and
// rely on brain_api's SPA fallback to serve ``index.html`` for any unmatched
// ``/browse/<path>/`` URL — the client router then resolves the path.

import { BrowsePathClient } from "./browse-path-client";

// Empty ``generateStaticParams`` + the default ``dynamicParams = false``
// under ``output: "export"`` means unknown paths 404 at Next.js — brain_api's
// SPA fallback picks those up and serves ``index.html`` so the client router
// takes over.
export async function generateStaticParams(): Promise<{ path: string[] }[]> {
  // Single placeholder so static export emits one ``/browse/_/`` bundle.
  // Real paths are served via brain_api's SPA fallback.
  return [{ path: ["_"] }];
}

export default function BrowsePathPage(): React.ReactElement {
  return <BrowsePathClient />;
}
