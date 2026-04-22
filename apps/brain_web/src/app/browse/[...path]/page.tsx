import { redirect } from "next/navigation";

import { BrowseScreen } from "@/components/browse/browse-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /browse/<path> — specific-note route (server component).
 *
 * Next.js 15 delivers catch-all ``params`` as a Promise. We rejoin
 * the segments into the original vault-relative path before
 * handing it to the client screen.
 */

interface BrowsePathPageProps {
  params: Promise<{ path: string[] }>;
}

export default async function BrowsePathPage({
  params,
}: BrowsePathPageProps): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  const { path } = await params;
  const joined = path.join("/");
  return <BrowseScreen activePath={joined} />;
}
