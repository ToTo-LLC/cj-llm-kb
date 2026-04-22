import { redirect } from "next/navigation";

import { BrowseScreen } from "@/components/browse/browse-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /browse — default landing (server component).
 *
 * Token gate mirrors the chat route. When no path is supplied the
 * client ``<BrowseScreen />`` resolves the first scoped note as
 * the active one; when there's literally nothing in the vault, it
 * renders the empty state.
 */
export default async function BrowseIndexPage(): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  return <BrowseScreen />;
}
