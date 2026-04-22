"use client";

// /chat — new-thread route (Client Component, Plan 08 Task 2).
//
// Port from the old server-component pattern: the token now lives in the
// ``useTokenStore`` Zustand slice (populated by the bootstrap effect) +
// ``useBootstrap()``. First-run is handled upstream by ``<BootstrapProvider>``
// pushing the user to /setup/ before the chat page ever renders, so by the
// time we get here the token is either present or the BootGate is showing
// the "Starting brain…" / error state.
//
// ``token={null}`` is still a legal prop for ChatScreen — the ``useChatWebSocket``
// hook stays inert until a real token arrives, which matches the old
// "redirect to /setup" behaviour without actually navigating.

import { ChatScreen } from "@/components/chat/chat-screen";
import { useBootstrap } from "@/lib/bootstrap/bootstrap-context";

export default function ChatPage(): React.ReactElement {
  const { token } = useBootstrap();
  return <ChatScreen threadId={null} token={token} />;
}
