import { redirect } from "next/navigation";

import { ChatScreen } from "@/components/chat/chat-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /chat — "new thread" route (server component).
 *
 * Reads the per-run API token from ``.brain/run/api-secret.txt`` on the
 * server so it never round-trips through a browser fetch. When the
 * token is missing (first-run before ``brain_api`` has started), we
 * redirect to the setup wizard — chat without a token would just
 * render a perma-"reconnecting" socket.
 *
 * Delegates to the client ``<ChatScreen />`` which owns the WS hook
 * lifecycle and the composition of Transcript + Composer + sub-header.
 * Passing ``threadId={null}`` tells ChatScreen this is the new-thread
 * variant — the hook stays inert until the backend creates a thread
 * and navigates to ``/chat/<id>``.
 */
export default async function ChatPage(): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  return <ChatScreen threadId={null} token={token} />;
}
