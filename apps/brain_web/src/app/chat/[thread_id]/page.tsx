// /chat/<thread_id> — Server Component page wrapper (Plan 08 Task 2).
//
// Static export (``output: "export"``) requires every dynamic segment to
// declare ``generateStaticParams()`` from a Server Component. We return an
// empty array to tell Next.js "there are no pre-rendered thread ids" — at
// runtime, brain_api's SPA fallback serves ``index.html`` for any unmatched
// ``/chat/<id>/`` path and the client router takes over.
//
// This file intentionally stays server-side because ``generateStaticParams``
// can't be colocated with ``"use client"``. All real rendering + state lives
// in ``<ChatThreadClient />``; this file is a pass-through shell.

import { ChatThreadClient } from "./chat-thread-client";

// ``generateStaticParams()`` returns empty: no thread ids are pre-rendered.
// ``dynamicParams`` defaults to ``false`` under ``output: "export"``, which
// means unknown thread_ids 404 at the Next.js layer. That's intentional —
// brain_api's SPA fallback upstream catches /chat/<id>/ and serves
// ``index.html`` so the client router resolves the path. See
// ``packages/brain_api/src/brain_api/static_ui.py`` for the fallback rules.
export async function generateStaticParams(): Promise<{ thread_id: string }[]> {
  // Pre-render a single placeholder ``_`` so Next.js has at least one output
  // to write for the dynamic segment under ``output: "export"``. brain_api's
  // SPA fallback serves ``index.html`` for any real thread id, so the
  // placeholder never gets hit at runtime.
  return [{ thread_id: "_" }];
}

export default function ChatThreadPage(): React.ReactElement {
  return <ChatThreadClient />;
}
