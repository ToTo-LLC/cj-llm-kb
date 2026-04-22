"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import { renderBody } from "@/lib/chat/rendering";
import type { ChatMessage } from "@/lib/state/chat-store";
import type { ChatMode } from "@/lib/ws/events";

import { InlinePatchCard } from "./inline-patch-card";
import { MsgActions } from "./msg-actions";
import { ToolCall } from "./tool-call";

/**
 * Message — one transcript row (user OR assistant).
 *
 * Visual contract ported from v3:
 *   - Role strip: avatar + "You" / "brain" + (assistant) mode chip +
 *     timestamp + (assistant) cost.
 *   - Body rendered via ``renderBody`` (inline wikilinks + bold + code
 *     + italic).
 *   - Assistant-only: tool calls render above the body (collapsible),
 *     inline patch card renders below the body.
 *   - Assistant-only, non-streaming: MsgActions visible on hover /
 *     focus.
 *   - Streaming mode (``isStreaming + streamingText``): body shows the
 *     accumulated streaming text with a caret span. The chat-store
 *     keeps ``msg.body`` empty until turn_end commits, so we read
 *     ``streamingText`` instead.
 */

const MODE_LABELS: Record<ChatMode, string> = {
  ask: "Ask",
  brainstorm: "Brainstorm",
  draft: "Draft",
};

export interface MessageProps {
  msg: ChatMessage;
  /** Last-message streaming text from chat-store; only read when isStreaming. */
  streamingText?: string;
  /** True while the assistant is still typing this message. */
  isStreaming?: boolean;
}

export function Message({
  msg,
  streamingText,
  isStreaming,
}: MessageProps): React.ReactElement {
  const isUser = msg.role === "user";
  const body = isStreaming ? (streamingText ?? "") : msg.body;
  const mode = msg.mode ?? "ask";

  return (
    <div
      className="group relative flex flex-col gap-1 py-3"
      data-role={msg.role}
    >
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <div
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-medium",
            isUser
              ? "bg-surface-3 text-foreground"
              : "bg-tt-cyan text-background",
          )}
          aria-hidden="true"
        >
          {isUser ? "CJ" : ""}
        </div>
        <span className="font-medium text-foreground">
          {isUser ? "You" : "brain"}
        </span>
        {!isUser && (
          <span className="rounded-sm bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-foreground">
            {MODE_LABELS[mode]}
          </span>
        )}
        <span>{msg.ts}</span>
        {msg.cost !== undefined && <span>· ${msg.cost.toFixed(3)}</span>}
      </div>

      <div className="ml-8 text-sm text-foreground">
        {!isUser &&
          msg.toolCalls &&
          msg.toolCalls.length > 0 &&
          msg.toolCalls.map((c) => <ToolCall key={c.id} call={c} />)}

        <div className="leading-relaxed">
          {renderBody(body)}
          {isStreaming && (
            <span
              className="stream-caret ml-0.5 inline-block h-4 w-1 animate-pulse bg-foreground align-middle"
              aria-hidden="true"
            />
          )}
        </div>

        {!isUser && msg.proposedPatch && (
          <InlinePatchCard patch={msg.proposedPatch} />
        )}
      </div>

      {!isUser && !isStreaming && (
        <MsgActions msg={msg} className="ml-8 mt-1" />
      )}
    </div>
  );
}
