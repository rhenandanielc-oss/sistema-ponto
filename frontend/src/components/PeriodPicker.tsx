import { presetPeriod, type Period, type PeriodPreset } from "../lib/period";

const PRESETS: { value: PeriodPreset; label: string }[] = [
  { value: "today", label: "Hoje" },
  { value: "week", label: "Semana" },
  { value: "month", label: "Mês" },
  { value: "custom", label: "Período" },
];

export function PeriodPicker({
  preset,
  period,
  onChange,
}: {
  preset: PeriodPreset;
  period: Period;
  onChange: (preset: PeriodPreset, period: Period) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5" role="group" aria-label="Período">
        {PRESETS.map((p) => (
          <button
            key={p.value}
            type="button"
            aria-pressed={preset === p.value}
            className={`rounded px-3 py-1.5 text-sm ${
              preset === p.value ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
            onClick={() => onChange(p.value, p.value === "custom" ? period : presetPeriod(p.value))}
          >
            {p.label}
          </button>
        ))}
      </div>
      {preset === "custom" && (
        <>
          <input
            type="date"
            aria-label="Data inicial"
            className="input w-auto"
            value={period.from}
            onChange={(e) => onChange("custom", { ...period, from: e.target.value })}
          />
          <span className="pb-2 text-sm text-slate-500">até</span>
          <input
            type="date"
            aria-label="Data final"
            className="input w-auto"
            value={period.to}
            onChange={(e) => onChange("custom", { ...period, to: e.target.value })}
          />
        </>
      )}
    </div>
  );
}
