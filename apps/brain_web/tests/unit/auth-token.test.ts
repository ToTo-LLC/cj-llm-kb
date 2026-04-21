import { beforeEach, describe, expect, test, vi } from "vitest";

const { readFileMock } = vi.hoisted(() => ({
  readFileMock: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  default: { readFile: readFileMock },
  readFile: readFileMock,
}));
vi.mock("node:os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));

import { invalidateTokenCache, readToken } from "@/lib/auth/token";

describe("readToken", () => {
  beforeEach(() => {
    invalidateTokenCache();
    readFileMock.mockReset();
    delete process.env.BRAIN_VAULT_ROOT;
  });

  test("reads token and strips whitespace", async () => {
    readFileMock.mockResolvedValue("abc123\n");
    const token = await readToken();
    expect(token).toBe("abc123");
  });

  test("returns null when file missing (ENOENT)", async () => {
    const err: Error & { code?: string } = new Error("ENOENT");
    err.code = "ENOENT";
    readFileMock.mockRejectedValue(err);
    const token = await readToken();
    expect(token).toBeNull();
  });

  test("caches after first successful read", async () => {
    readFileMock.mockResolvedValue("abc123");
    await readToken();
    await readToken();
    expect(readFileMock).toHaveBeenCalledTimes(1);
  });

  test("respects BRAIN_VAULT_ROOT env var", async () => {
    process.env.BRAIN_VAULT_ROOT = "/custom/vault";
    readFileMock.mockResolvedValue("xyz");
    await readToken();
    expect(readFileMock).toHaveBeenCalledWith(
      expect.stringContaining("/custom/vault/.brain/run/api-secret.txt"),
      "utf-8",
    );
  });
});
