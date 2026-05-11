import { describe, test, expect } from "vitest";
import { AUTONOMY_CATEGORIES } from "@/lib/api/tools";
import fixture from "../fixtures/autonomy-categories.json";

describe("AutonomyCategory drift detection", () => {
  test("AUTONOMY_CATEGORIES matches the committed fixture (brain_core ↔ TS sync gate)", () => {
    // Sort both sides so the assertion is order-independent.
    const expected = [...fixture].sort();
    const actual = [...AUTONOMY_CATEGORIES].sort();
    expect(actual).toEqual(expected);
  });
});
