import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { OfflineBanner } from "@/components/system/offline-banner";

/**
 * OfflineBanner (Plan 07 Task 12): system-level banner shown above the app
 * grid while the WS is offline or reconnecting. Copy matches the v3 design.
 */

describe("OfflineBanner", () => {
  test("offline copy", () => {
    render(<OfflineBanner state="offline" />);
    expect(screen.getByText(/brain is offline\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/your last turn didn't send\. reads from vault still work\./i),
    ).toBeInTheDocument();
  });

  test("reconnecting copy", () => {
    render(<OfflineBanner state="reconnecting" />);
    expect(screen.getByText(/reconnecting…/i)).toBeInTheDocument();
    expect(
      screen.getByText(/dropped connection to the local runtime\. queued turns will resend\./i),
    ).toBeInTheDocument();
  });
});
