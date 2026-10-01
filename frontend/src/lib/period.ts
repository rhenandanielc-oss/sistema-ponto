/** Atalhos de período (hoje, semana, mês) — datas inclusivas, como a API espera. */

export type PeriodPreset = "today" | "week" | "month" | "custom";

export interface Period {
  from: string;
  to: string;
}

export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function presetPeriod(preset: Exclude<PeriodPreset, "custom">, today = new Date()): Period {
  const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (preset === "today") return { from: toIsoDate(base), to: toIsoDate(base) };
  if (preset === "week") {
    const monday = new Date(base);
    monday.setDate(base.getDate() - ((base.getDay() + 6) % 7));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { from: toIsoDate(monday), to: toIsoDate(sunday) };
  }
  const first = new Date(base.getFullYear(), base.getMonth(), 1);
  const last = new Date(base.getFullYear(), base.getMonth() + 1, 0);
  return { from: toIsoDate(first), to: toIsoDate(last) };
}
