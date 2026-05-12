import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/**
 * SourceRow (Plan 07 Task 17) — a single inbox row.
 *
 * Each status variant (queued / classifying / integrating / failed)
 * renders distinct styling: a status pill with the right label, an
 * optional progress bar, and — for ``failed`` — an error line plus a
 * Retry button.
 */

import { SourceRow } from "@/components/inbox/source-row";
import type { IngestSource } from "@/lib/state/inbox-store";

function mkSource(extra: Partial<IngestSource> = {}): IngestSource {
  return {
    id: "s-1",
    source: "https://example.com/x",
    title: "Silent buyers — research note",
    type: "url",
    status: "queued",
    domain: "research",
    progress: 0,
    at: "2026-04-21T10:00:00Z",
    ...extra,
  };
}

describe("SourceRow", () => {
  test("queued status renders the queued label with 0% progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "queued", progress: 0 })} />,
    );
    const row = screen.getByTestId("source-row");
    expect(row).toHaveAttribute("data-status", "queued");
    // Pill label visible.
    expect(screen.getByText(/^queued$/i)).toBeInTheDocument();
    // Progress bar fill width mirrors progress=0.
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill).not.toBeNull();
    expect(fill!.style.width).toBe("0%");
  });

  test("classifying status renders the classifying label with partial progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "classifying", progress: 40 })} />,
    );
    expect(screen.getByTestId("source-row")).toHaveAttribute(
      "data-status",
      "classifying",
    );
    expect(screen.getByText(/^classifying$/i)).toBeInTheDocument();
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill!.style.width).toBe("40%");
  });

  test("integrating status renders distinct label with high progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "integrating", progress: 85 })} />,
    );
    expect(screen.getByTestId("source-row")).toHaveAttribute(
      "data-status",
      "integrating",
    );
    expect(screen.getByText(/^integrating$/i)).toBeInTheDocument();
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill!.style.width).toBe("85%");
  });

  // Plan 19 T3 (D4): the ``done`` row's cost badge should render when
  // ``cost > 0`` and be suppressed for ``cost === 0`` and ``cost ===
  // undefined``. The strict ``cost > 0`` form is decisive about which
  // values mean "no badge" — cached / zero-token rows the backend emits
  // as 0.0 used to render as the visually-noisy and semantically
  // ambiguous "$0.000".
  test("done status renders the cost badge when cost > 0", () => {
    render(
      <SourceRow
        source={mkSource({
          status: "done",
          progress: 100,
          domain: "research",
          cost: 0.123,
        })}
      />,
    );
    expect(screen.getByText(/\$0\.123/)).toBeInTheDocument();
  });

  test("done status suppresses the cost badge when cost === 0", () => {
    render(
      <SourceRow
        source={mkSource({
          status: "done",
          progress: 100,
          domain: "research",
          cost: 0,
        })}
      />,
    );
    // No "$" cost segment anywhere on the row — the "Filed to <domain>"
    // line stands alone.
    expect(screen.queryByText(/\$0\.000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/·\s*\$/)).not.toBeInTheDocument();
  });

  test("done status suppresses the cost badge when cost is undefined", () => {
    render(
      <SourceRow
        source={mkSource({
          status: "done",
          progress: 100,
          domain: "research",
          // cost intentionally omitted — IngestSource.cost is optional.
        })}
      />,
    );
    expect(screen.queryByText(/·\s*\$/)).not.toBeInTheDocument();
  });

  // Plan 24 T5: new SourceType values (`docx`, `pptx`) need a dedicated
  // icon + label in the type badge. The badge has two readable
  // surfaces: the label text (DOCX / PPTX) AND the Lucide icon
  // (FileText for docx, Presentation for pptx). We assert on the
  // label here AND the icon's testid so a future swap of either side
  // fails RED instead of silently degrading to a generic FILE row.
  test("docx type renders the DOCX label with the FileText icon", () => {
    render(
      <SourceRow
        source={mkSource({
          type: "docx",
          status: "done",
          progress: 100,
          domain: "research",
          title: "Q4-strategy.docx",
        })}
      />,
    );
    expect(screen.getByText(/^DOCX$/)).toBeInTheDocument();
    // Distinct testid added in TypeIcon for the docx case — guarantees
    // the FileText branch ran, not a fall-through to FileIcon.
    expect(screen.getByTestId("type-icon-docx")).toBeInTheDocument();
  });

  test("pptx type renders the PPTX label with the Presentation icon", () => {
    render(
      <SourceRow
        source={mkSource({
          type: "pptx",
          status: "done",
          progress: 100,
          domain: "research",
          title: "all-hands-2026.pptx",
        })}
      />,
    );
    expect(screen.getByText(/^PPTX$/)).toBeInTheDocument();
    // Distinct testid for the pptx case — Presentation glyph is the
    // intended visual differentiator from .docx in mixed inboxes.
    expect(screen.getByTestId("type-icon-pptx")).toBeInTheDocument();
  });

  test("failed status renders the error line AND a Retry button", () => {
    const onRetry = vi.fn();
    render(
      <SourceRow
        source={mkSource({
          status: "failed",
          progress: 0,
          error: "Upstream classifier returned 503",
        })}
        onRetry={onRetry}
      />,
    );
    const row = screen.getByTestId("source-row");
    expect(row).toHaveAttribute("data-status", "failed");
    // Error surface + retry affordance.
    expect(
      screen.getByText(/upstream classifier returned 503/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
