import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { PatchCard } from "@/components/pending/patch-card";
import type { PatchCardPatch } from "@/components/pending/patch-card";

/**
 * PatchCard (Plan 07 Task 16) — metadata-only row in the pending screen's
 * left list and in the chat-route right rail. The card receives a
 * UI-friendly subset of the backend envelope; ``brain_``-prefixed tool
 * names must render with the prefix stripped (``propose_note``, not
 * ``brain_propose_note``), and personal-domain chips must render a lock
 * icon. ``isNew`` paints the arrival-bell pulse.
 */

function mkPatch(extra: Partial<PatchCardPatch> = {}): PatchCardPatch {
  return {
    patch_id: "p-1",
    tool: "brain_propose_note",
    domain: "research",
    target_path: "research/notes/silent-buyer.md",
    reason: "New synthesis from today's interview",
    created_at: "2026-04-21T10:00:00Z",
    isNew: false,
    ...extra,
  };
}

describe("PatchCard", () => {
  test("renders metadata with the brain_ prefix stripped from the tool name", () => {
    render(
      <PatchCard
        patch={mkPatch()}
        selected={false}
        onSelect={vi.fn()}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    // Tool name without the brain_ prefix.
    expect(screen.getByText("propose_note")).toBeInTheDocument();
    // Target path renders verbatim.
    expect(
      screen.getByText("research/notes/silent-buyer.md"),
    ).toBeInTheDocument();
    // Reason line.
    expect(
      screen.getByText(/new synthesis from today/i),
    ).toBeInTheDocument();
  });

  test("domain chip renders with the personal lock icon when domain is personal", () => {
    const { container } = render(
      <PatchCard
        patch={mkPatch({ domain: "personal" })}
        selected={false}
        onSelect={vi.fn()}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    // Domain text rendered.
    expect(screen.getByText("personal")).toBeInTheDocument();
    // Lock icon present — lucide renders an SVG carrying the ``lucide-lock`` class.
    const lock = container.querySelector("svg.lucide-lock");
    expect(lock).not.toBeNull();
  });

  test("isNew=true paints the arrival-bell pulse badge", () => {
    const { container } = render(
      <PatchCard
        patch={mkPatch({ isNew: true })}
        selected={false}
        onSelect={vi.fn()}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    // Cards carry a data-new flag when isNew is true so CSS can paint the
    // pulse. We also render a labelled bell marker.
    const card = container.querySelector('[data-new="true"]');
    expect(card).not.toBeNull();
    expect(screen.getByLabelText(/new/i)).toBeInTheDocument();
  });
});
