import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/unit/setup.ts"],
    // Vitest defaults to ``tests/**`` — the e2e specs live alongside unit
    // tests under ``tests/e2e/`` and import from ``@playwright/test``,
    // which throws at collection time inside jsdom. Exclude them; they
    // run via ``pnpm e2e`` (Playwright test runner).
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
  },
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
});
