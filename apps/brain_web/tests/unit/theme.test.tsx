import { describe, expect, test, beforeEach } from "vitest";
import { render, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { ThemeProvider, useTheme } from "@/components/theme-provider";

function Harness({ onReady }: { onReady: (ctx: ReturnType<typeof useTheme>) => void }) {
  const ctx = useTheme();
  onReady(ctx);
  return <div>{ctx.theme}</div>;
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.density;
  });

  test("defaults to dark theme when localStorage empty", () => {
    const captured = { current: null as ReturnType<typeof useTheme> | null };
    render(
      <ThemeProvider>
        <Harness onReady={(c) => { captured.current = c; }} />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(captured.current?.theme).toBe("dark");
  });

  test("setTheme toggles to light and persists to localStorage", async () => {
    const ref = { setTheme: null as ((t: "dark" | "light") => void) | null };
    render(
      <ThemeProvider>
        <Harness onReady={(c) => { ref.setTheme = c.setTheme; }} />
      </ThemeProvider>,
    );
    await act(async () => { ref.setTheme!("light"); });
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("brain-theme")).toBe("light");
  });

  test("setDensity toggles to compact independently of theme", async () => {
    const ref = {
      setDensity: null as ((d: "comfortable" | "compact") => void) | null,
      theme: null as "dark" | "light" | null,
    };
    render(
      <ThemeProvider>
        <Harness
          onReady={(c) => {
            ref.setDensity = c.setDensity;
            ref.theme = c.theme;
          }}
        />
      </ThemeProvider>,
    );
    await act(async () => { ref.setDensity!("compact"); });
    expect(document.documentElement.dataset.density).toBe("compact");
    expect(localStorage.getItem("brain-density")).toBe("compact");
    // Theme must remain at its default (dark) — density is independent.
    expect(ref.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
