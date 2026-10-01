/** Formatação para exibição. Nenhum cálculo de jornada acontece no frontend (MASTER-PROMPT §8). */

export const WEEKDAYS = [
  { value: 0, short: "Seg", long: "Segunda" },
  { value: 1, short: "Ter", long: "Terça" },
  { value: 2, short: "Qua", long: "Quarta" },
  { value: 3, short: "Qui", long: "Quinta" },
  { value: 4, short: "Sex", long: "Sexta" },
  { value: 5, short: "Sáb", long: "Sábado" },
  { value: 6, short: "Dom", long: "Domingo" },
] as const;

export const RECORD_TYPE_LABELS: Record<string, string> = {
  ENTRY: "Entrada",
  LUNCH_EXIT: "Saída para almoço",
  LUNCH_RETURN: "Retorno do almoço",
  EXIT: "Saída",
};

export const DAY_STATUS_LABELS: Record<string, string> = {
  OK: "Completo",
  ABSENT: "Falta",
  INCOMPLETE: "Incompleto",
  IN_PROGRESS: "Em andamento",
  FUTURE: "Futuro",
  NONE: "—",
};

export const DAY_TYPE_LABELS: Record<string, string> = {
  WORKDAY: "Dia de trabalho",
  DAY_OFF: "Folga",
  HOLIDAY: "Feriado",
  NOT_EMPLOYED: "Fora do contrato",
};

export const FLAG_LABELS: Record<string, string> = {
  INSUFFICIENT_BREAK: "Intervalo insuficiente",
  HOLIDAY_WORK: "Trabalho em feriado",
  DAY_OFF_WORK: "Trabalho em folga",
};

/** 480 → "8h00"; com `signed`, 90 → "+1h30" e -20 → "-0h20". */
export function formatMinutes(minutes: number, signed = false): string {
  const sign = minutes < 0 ? "-" : signed && minutes > 0 ? "+" : "";
  const abs = Math.abs(minutes);
  return `${sign}${Math.floor(abs / 60)}h${String(abs % 60).padStart(2, "0")}`;
}

/** "2026-09-01" → "01/09/2026" (sem conversão de fuso: é uma data de calendário). */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return `${d}/${m}/${y}`;
}

/** Dia da semana de uma data de calendário "AAAA-MM-DD". */
export function weekdayOf(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  const jsDay = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)).getUTCDay(); // 0 = domingo
  return WEEKDAYS[(jsDay + 6) % 7]?.short ?? "";
}

/**
 * Hora de um instante que a API já devolve no fuso da empresa ("2026-09-01T08:02:13-03:00").
 * Lê a hora do próprio texto, para não depender do fuso do navegador.
 */
export function formatTime(isoInstant: string): string {
  return isoInstant.slice(11, 16);
}

export function formatDateTime(isoInstant: string): string {
  return `${formatDate(isoInstant.slice(0, 10))} ${formatTime(isoInstant)}`;
}

/** "08:00:00" → "08:00". */
export function shortTime(time: string): string {
  return time.slice(0, 5);
}

/** 7.5 → "7,50" (horas decimais, para multiplicar pelo valor da hora). */
export function formatDecimalHours(hours: number): string {
  return hours.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
