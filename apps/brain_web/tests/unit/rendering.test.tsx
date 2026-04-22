import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { renderBody } from "@/lib/chat/rendering";

/**
 * Inline-markdown parser used by chat messages. Plan 07 Task 14.
 *
 * Handles the four inline tokens brain's assistant emits:
 *   - ``[[wikilink]]``   → <a class="wikilink"> (broken = red variant)
 *   - ``**bold**``       → <strong>
 *   - `` `code` ``       → <code>
 *   - ``*italic*``       → <em>
 *
 * ``BROKEN_WIKILINKS`` is an empty Set for now — Plan 09's
 * brain_wikilink_status tool populates it (deferred per Task 25 sweep).
 */
describe("renderBody", () => {
  test("plain paragraph renders as a single <p>", () => {
    render(<div data-testid="wrap">{renderBody("hello world")}</div>);
    const wrap = screen.getByTestId("wrap");
    const paragraphs = wrap.querySelectorAll("p");
    expect(paragraphs).toHaveLength(1);
    expect(paragraphs[0]).toHaveTextContent("hello world");
  });

  test("wikilink renders as <a class='wikilink'> with the label as text", () => {
    render(<div data-testid="wrap">{renderBody("see [[fisher-ury]] for more")}</div>);
    const link = screen.getByRole("link", { name: "fisher-ury" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveClass("wikilink");
    expect(link).not.toHaveClass("broken");
  });

  test("broken wikilinks get the 'broken' class (Task 25 wires the source Set)", () => {
    // For Task 14 the broken-set is empty, so no wikilink should get the
    // `.broken` class. Plan 09 will fill the set; until then we assert the
    // fallback path.
    render(<div data-testid="wrap">{renderBody("link to [[future-work]] here")}</div>);
    const link = screen.getByRole("link", { name: "future-work" });
    expect(link).toHaveClass("wikilink");
    expect(link).not.toHaveClass("broken");
  });

  test("bold runs render as <strong>", () => {
    render(<div data-testid="wrap">{renderBody("the **deal-stall** pattern")}</div>);
    const wrap = screen.getByTestId("wrap");
    const strong = wrap.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong).toHaveTextContent("deal-stall");
  });

  test("inline code renders as <code>", () => {
    render(<div data-testid="wrap">{renderBody("run `brain doctor` first")}</div>);
    const wrap = screen.getByTestId("wrap");
    const code = wrap.querySelector("code");
    expect(code).not.toBeNull();
    expect(code).toHaveTextContent("brain doctor");
  });

  test("italic runs render as <em>", () => {
    render(<div data-testid="wrap">{renderBody("emphasize *just this* word")}</div>);
    const wrap = screen.getByTestId("wrap");
    const em = wrap.querySelector("em");
    expect(em).not.toBeNull();
    expect(em).toHaveTextContent("just this");
  });
});
