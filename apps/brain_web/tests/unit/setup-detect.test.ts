import { beforeEach, describe, expect, test, vi } from "vitest";

// Hoisted mocks — factory refs shared across mocked modules so tests can
// rewire behaviour per-case without reimporting.
const { accessMock, readTokenMock } = vi.hoisted(() => ({
  accessMock: vi.fn(),
  readTokenMock: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  default: { access: accessMock },
  access: accessMock,
}));
vi.mock("node:os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));
vi.mock("@/lib/auth/token", () => ({
  readToken: readTokenMock,
}));

import { detectSetupStatus } from "@/lib/setup/detect";

describe("detectSetupStatus", () => {
  beforeEach(() => {
    accessMock.mockReset();
    readTokenMock.mockReset();
    delete process.env.BRAIN_VAULT_ROOT;
  });

  test("missing BRAIN.md → isFirstRun=true", async () => {
    // Vault exists, BRAIN.md does not. access() succeeds for vault root but
    // fails for BRAIN.md path.
    accessMock.mockImplementation(async (p: string) => {
      if (p.endsWith("BRAIN.md")) throw new Error("ENOENT");
      return undefined;
    });
    readTokenMock.mockResolvedValue("tok");
    const status = await detectSetupStatus();
    expect(status.hasBrainMd).toBe(false);
    expect(status.isFirstRun).toBe(true);
  });

  test("vault + BRAIN.md + token all present → isFirstRun=false", async () => {
    accessMock.mockResolvedValue(undefined);
    readTokenMock.mockResolvedValue("tok");
    const status = await detectSetupStatus();
    expect(status.hasVault).toBe(true);
    expect(status.hasBrainMd).toBe(true);
    expect(status.hasToken).toBe(true);
    expect(status.hasApiKey).toBe(true);
    expect(status.isFirstRun).toBe(false);
  });

  test("missing token → isFirstRun=true", async () => {
    accessMock.mockResolvedValue(undefined); // vault + BRAIN.md exist
    readTokenMock.mockResolvedValue(null);
    const status = await detectSetupStatus();
    expect(status.hasToken).toBe(false);
    expect(status.hasApiKey).toBe(false);
    expect(status.isFirstRun).toBe(true);
  });

  test("missing vault root → isFirstRun=true", async () => {
    // access() rejects for everything — vault folder doesn't even exist.
    accessMock.mockRejectedValue(new Error("ENOENT"));
    readTokenMock.mockResolvedValue(null);
    const status = await detectSetupStatus();
    expect(status.hasVault).toBe(false);
    expect(status.hasBrainMd).toBe(false);
    expect(status.isFirstRun).toBe(true);
  });
});
