import { redirect } from "next/navigation";

import { ChatScreen } from "@/components/chat/chat-screen";
import { readToken } from "@/lib/auth/token";

/**
 * /chat/<thread_id> — existing-thread route (server component).
 *
 * Mirrors ``/chat``'s token handling: reads the per-run API token on
 * the server, redirects to setup if missing, and passes token +
 * thread id to the client ``<ChatScreen />``.
 *
 * Next.js 15 passes ``params`` as a Promise to server components —
 * awaiting it unwraps the thread id.
 */

type Params = { thread_id: string };

interface ChatThreadPageProps {
  params: Promise<Params>;
}

export default async function ChatThreadPage({
  params,
}: ChatThreadPageProps): Promise<JSX.Element> {
  const token = await readToken();
  if (!token) redirect("/setup");
  const { thread_id } = await params;
  return <ChatScreen threadId={thread_id} token={token} />;
}
