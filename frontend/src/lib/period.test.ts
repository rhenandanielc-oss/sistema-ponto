import { describe, expect, it } from "vitest";

import { presetPeriod } from "./period";

describe("atalhos de período (inclusivos)", () => {
  const thursday = new Date(2026, 8, 10, 15, 0); // 10/09/2026

  it("hoje", () => {
    expect(presetPeriod("today", thursday)).toEqual({ from: "2026-09-10", to: "2026-09-10" });
  });

  it("semana de segunda a domingo", () => {
    expect(presetPeriod("week", thursday)).toEqual({ from: "2026-09-07", to: "2026-09-13" });
    const sunday = new Date(2026, 8, 13);
    expect(presetPeriod("week", sunday)).toEqual({ from: "2026-09-07", to: "2026-09-13" });
  });

  it("mês inteiro", () => {
    expect(presetPeriod("month", thursday)).toEqual({ from: "2026-09-01", to: "2026-09-30" });
    expect(presetPeriod("month", new Date(2028, 1, 10))).toEqual({ from: "2028-02-01", to: "2028-02-29" });
  });
});
