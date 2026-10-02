import { describe, expect, it } from "vitest";

import { clockSkewMinutes, clockWarning } from "./clock";

describe("relógio do servidor", () => {
  const device = Date.parse("2026-10-01T08:00:00-03:00");

  it("calcula a diferença considerando o fuso da resposta", () => {
    expect(clockSkewMinutes("2026-10-01T08:00:20-03:00", device)).toBe(0);
    expect(clockSkewMinutes("2026-10-01T11:05:00Z", device)).toBe(5);
    expect(clockSkewMinutes("2026-10-01T07:50:00-03:00", device)).toBe(-10);
  });

  it("só avisa acima de 2 minutos", () => {
    expect(clockWarning(2)).toBeNull();
    expect(clockWarning(-2)).toBeNull();
    expect(clockWarning(5)).toContain("5 min adiantado");
    expect(clockWarning(-10)).toContain("10 min atrasado");
  });
});
