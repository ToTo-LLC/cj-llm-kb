"use client";

/**
 * Plan 16 Task 6 / D6 — BroadcastChannel cross-tab pubsub helper.
 *
 * Thin module-private layer wired into both ``domains-store.ts`` and
 * ``cross-domain-gate-store.ts``. On any ``set()`` that mutates one of
 * those stores, the store posts to its channel; on inbound messages,
 * the store applies the payload via an ``_internalSet`` flag-guarded
 * setter so the apply does NOT re-broadcast (avoids ping-pong).
 *
 * Why a helper module rather than inlining the BroadcastChannel calls
 * in each store:
 *
 *   1. **SSR safety.** Next.js renders pages on the server where
 *      ``BroadcastChannel`` is undefined. The helper's first line is
 *      a ``typeof BroadcastChannel === "undefined"`` guard that
 *      returns a no-op pubsub so SSR never throws on store import.
 *      Each store would otherwise have to repeat the guard.
 *   2. **Test seam.** The two new pin tests (``domains-store-broadcast``
 *      + ``cross-domain-gate-store-broadcast``) can simulate a peer
 *      tab by creating their own ``BroadcastChannel`` with the same
 *      channel name and posting through it. They never have to reach
 *      into the store's private channel reference.
 *   3. **Single shape.** The "post on mutate, don't echo on inbound"
 *      pattern repeats across both stores; centralizing the pubsub
 *      construction means the no-echo flag plumbing lives in the
 *      store (where the ``set()`` happens), and the helper stays
 *      a 10-line wrapper.
 *
 * Channel names are caller-supplied and MUST be distinct between
 * stores to avoid cross-contamination. ``domains-store`` uses
 * ``"brain-domains"``; ``cross-domain-gate-store`` uses
 * ``"brain-cross-domain-gate"``. (See each store's call site for the
 * binding.)
 *
 * Per the BroadcastChannel spec, a sender does NOT receive its own
 * postMessage — only OTHER channel instances with the same name in
 * the same browser get the event. This is precisely the behavior we
 * want: tab A's store mutates and posts; tab B's store (a different
 * BroadcastChannel instance) receives. Within a single tab, the
 * store's own channel never re-fires its own posts back into itself,
 * so the no-echo guard in the store ONLY has to defend against the
 * inbound-from-peer case calling ``_internalSet`` and then re-posting.
 */

export interface ChannelPubsub<T> {
  /** Broadcast ``data`` to all peer ``BroadcastChannel`` instances
   *  with the same name in this browser (other tabs / windows). On
   *  SSR or in environments without BroadcastChannel support, this
   *  is a no-op. */
  post: (data: T) => void;
  /** Close the underlying BroadcastChannel (releases the channel for
   *  GC). Tests use this in cleanup; production code typically holds
   *  the channel open for the page lifetime. On SSR / unsupported
   *  environments this is a no-op. */
  close: () => void;
}

/**
 * Create a typed pubsub bound to a named ``BroadcastChannel``.
 *
 * - On SSR / environments without BroadcastChannel support, returns
 *   a no-op pubsub (``post`` and ``close`` are silent). This keeps
 *   store import side-effect-safe under Next.js server rendering and
 *   under any future Node.js test runner that doesn't pull in
 *   jsdom's BroadcastChannel.
 * - In the browser (and jsdom 22+), creates a fresh BroadcastChannel
 *   bound to ``name`` and wires ``onMessage`` to the handler. The
 *   caller is responsible for guarding against echoes (see store
 *   call sites for the ``_isInternalUpdate`` flag pattern).
 */
export function createChannelPubsub<T>(
  name: string,
  onMessage: (data: T) => void,
): ChannelPubsub<T> {
  if (typeof BroadcastChannel === "undefined") {
    return { post: () => {}, close: () => {} };
  }
  const channel = new BroadcastChannel(name);
  channel.onmessage = (e: MessageEvent<T>) => onMessage(e.data);
  return {
    post: (data) => channel.postMessage(data),
    close: () => channel.close(),
  };
}
