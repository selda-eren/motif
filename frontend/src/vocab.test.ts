import { describe, expect, it } from "vitest";
import { passageNo, roman } from "./vocab";

describe("numerals", () => {
  it("writes Roman numerals correctly for any size (stages and book chapters only)", () => {
    const cases: [number, string][] = [[1, "I"], [4, "IV"], [9, "IX"], [16, "XVI"], [40, "XL"], [49, "XLIX"], [50, "L"], [86, "LXXXVI"],
      [90, "XC"], [99, "XCIX"], [100, "C"], [400, "CD"], [1994, "MCMXCIV"]];
    for (const [n, r] of cases) expect(roman(n)).toBe(r);
  });

  it("never produces the old runs of Xs (XXXXXXXXVI) for the 86 passages of a long book", () => {
    for (let n = 1; n <= 200; n++) expect(roman(n)).not.toMatch(/X{4}/);
  });

  it("shows passage numbers as ordinary digits from the 0-based index", () => {
    expect(passageNo(0)).toBe("1");
    expect(passageNo(85)).toBe("86");
    for (let i = 0; i < 300; i++) expect(passageNo(i)).toBe(String(i + 1));
  });
});
