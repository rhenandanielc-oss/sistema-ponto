import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatDateTime,
  formatDecimalHours,
  formatMinutes,
  formatMoney,
  formatTime,
  parseMoney,
  weekdayOf,
} from "./format";

describe("formatação", () => {
  it("formata minutos como horas", () => {
    expect(formatMinutes(480)).toBe("8h00");
    expect(formatMinutes(420)).toBe("7h00");
    expect(formatMinutes(90, true)).toBe("+1h30");
    expect(formatMinutes(-20, true)).toBe("-0h20");
    expect(formatMinutes(0, true)).toBe("0h00");
  });

  it("formata horas decimais para multiplicar pelo valor da hora", () => {
    expect(formatDecimalHours(25)).toBe("25,00");
    expect(formatDecimalHours(7.5)).toBe("7,50");
    expect(formatDecimalHours(1.33)).toBe("1,33");
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

describe("dinheiro", () => {
  it("formata centavos em reais", () => {
    expect(formatMoney(600).replace(/\s/g, " ")).toBe("R$ 6,00");
    expect(formatMoney(123456).replace(/\s/g, " ")).toBe("R$ 1.234,56");
  });

  it("lê o valor digitado", () => {
    expect(parseMoney("6")).toBe(600);
    expect(parseMoney("6,5")).toBe(650);
    expect(parseMoney("R$ 1.234,56")).toBe(123456);
    expect(parseMoney("abc")).toBeNull();
    expect(parseMoney("6,555")).toBeNull();
  });
});
