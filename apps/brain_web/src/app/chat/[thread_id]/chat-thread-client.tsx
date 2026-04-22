"use client";

// /chat/<thread_id> — Client Component renderer (Plan 08 Task 2).
//
// Split out from ``page.tsx`` because ``generateStaticParams()`` must live
// in a Server Component, but the actual chat screen + hook lifecycle are
// client-only.
//
// ## Why ``usePathname()`` instead of ``useParams()``
//
// Static export pre-renders a single placeholder (``thread_id = "_"``).
// brain_api's SPA fallback serves that placeholder's HTML for any live
// ``/chat/<real-id>/`` URL. The Next.js client router hydrates with the
// build-time params — so ``useParams()`` returns ``{thread_id: "_"}`` even
// though ``window.location.pathname`` is ``/chat/abc/``. That's a known
// static-export limitation; the fix is to derive the thread id from the
// URL path directly.

import { usePathname } from "next/navigation";

import { ChatScreen } from "@/components/chat/chat-screen";
import { useBootstrap } from "@/lib/bootstrap/bootstrap-context";

export function ChatThreadClient(): React.ReactElement {
  const { token } = useBootstrap();
  const pathname = usePathname();
  // Expected shape: /chat/<thread_id>/ (trailing slash is added by
  // ``trailingSlash: true`` on the Next.js config).
  const match = pathname.match(/^\/chat\/([^/]+)\/?$/);
  const threadId =
    match && match[1] !== "_" && match[1] !== undefined ? match[1] : null;
  return <ChatScreen threadId={threadId} token={token} />;
}
