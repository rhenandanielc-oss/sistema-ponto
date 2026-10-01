import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime, formatMinutes, formatTime, weekdayOf } from "./format";

describe("formatação", () => {
  it("formata minutos como horas", () => {
    expect(formatMinutes(480)).toBe("8h00");
    expect(formatMinutes(420)).toBe("7h00");
    expect(formatMinutes(90, true)).toBe("+1h30");
    expect(formatMinutes(-20, true)).toBe("-0h20");
    expect(formatMinutes(0, true)).toBe("0h00");
  });

  it("formata datas de calendário sem depender do fuso do navegador", () => {
    expect(formatDate("2026-09-01")).toBe("01/09/2026");
    expect(weekdayOf("2026-09-01")).toBe("Ter");
    expect(weekdayOf("2026-09-06")).toBe("Dom");
  });

  it("lê a hora do instante já no fuso da empresa", () => {
    expect(formatTime("2026-09-01T08:02:13-03:00")).toBe("08:02");
    expect(formatDateTime("2026-09-01T23:30:00-03:00")).toBe("01/09/2026 23:30");
  });
});
