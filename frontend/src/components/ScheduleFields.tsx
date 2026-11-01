import type { Schemas } from "../api/client";
import { WEEKDAYS, shortTime } from "../lib/format";

/** Horário de um dia que foge do horário padrão (ex.: sábado 07:30–14:30). */
export interface DayTimes {
  start_time: string;
  end_time: string;
  lunch_minutes: number;
}

/** Valores do formulário de horário fixo, como o administrador digita. */
export interface ScheduleForm {
  weekdays: number[];
  start_time: string;
  end_time: string;
  lunch_minutes: number;
  weekly_day_off: boolean;
  /** Dias com horário diferente do padrão, por dia da semana (0 = segunda). */
  overrides: Record<number, DayTimes>;
}

export const DEFAULT_SCHEDULE: ScheduleForm = {
  weekdays: [0, 1, 2, 3, 4],
  start_time: "08:00",
  end_time: "17:00",
  lunch_minutes: 60,
  weekly_day_off: false,
  overrides: {},
};

/** Corpo esperado pela API: forma simples, ou dia a dia quando algum dia tem horário diferente. */
export function scheduleToApi(form: ScheduleForm) {
  const weekdays = [...form.weekdays].sort((a, b) => a - b);
  const common: DayTimes = { start_time: form.start_time, end_time: form.end_time, lunch_minutes: form.lunch_minutes };
  if (!weekdays.some((d) => form.overrides[d])) {
    return { weekdays, ...common, weekly_day_off: form.weekly_day_off };
  }
  return {
    days: weekdays.map((weekday) => ({ weekday, ...(form.overrides[weekday] ?? common) })),
    weekly_day_off: form.weekly_day_off,
  };
}

/** Monta o formulário a partir do horário salvo: o horário mais comum vira o padrão, os outros viram exceção. */
export function scheduleFromApi(schedule: Schemas["ScheduleOut"]): ScheduleForm {
  const key = (d: DayTimes) => `${d.start_time}|${d.end_time}|${d.lunch_minutes}`;
  const days = schedule.days.map((d) => ({
    weekday: d.weekday,
    times: { start_time: shortTime(d.start_time), end_time: shortTime(d.end_time), lunch_minutes: d.lunch_minutes },
  }));
  const counts = new Map<string, number>();
  for (const d of days) counts.set(key(d.times), (counts.get(key(d.times)) ?? 0) + 1);
  let mostCommon = days[0];
  if (!mostCommon) return { ...DEFAULT_SCHEDULE, weekly_day_off: schedule.weekly_day_off };
  for (const d of days) {
    if ((counts.get(key(d.times)) ?? 0) > (counts.get(key(mostCommon.times)) ?? 0)) mostCommon = d;
  }
  const overrides: Record<number, DayTimes> = {};
  const standard = mostCommon.times;
  for (const d of days) if (key(d.times) !== key(standard)) overrides[d.weekday] = d.times;
  return {
    weekdays: days.map((d) => d.weekday),
    ...standard,
    weekly_day_off: schedule.weekly_day_off,
    overrides,
  };
}

export function ScheduleFields({
  value,
  onChange,
}: {
  value: ScheduleForm;
  onChange: (value: ScheduleForm) => void;
}) {
  const toggle = (day: number) =>
    onChange({
      ...value,
      weekdays: value.weekdays.includes(day) ? value.weekdays.filter((d) => d !== day) : [...value.weekdays, day],
    });

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="label">Dias de trabalho</legend>
        <div className="flex flex-wrap gap-2">
          {WEEKDAYS.map((day) => {
            const checked = value.weekdays.includes(day.value);
            return (
              <label
                key={day.value}
                className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${
                  checked ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-600"
                }`}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={checked}
                  onChange={() => toggle(day.value)}
                  aria-label={day.long}
                />
                {day.short}
              </label>
            );
          })}
        </div>
        <p className="mt-1 text-xs text-slate-500">Trabalho em dia não marcado conta como hora extra.</p>
        <label className="mt-3 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={value.weekly_day_off}
            onChange={(e) => onChange({ ...value, weekly_day_off: e.target.checked })}
          />
          <span>
            <span className="font-medium">Folga semanal em qualquer dia</span>
            <span className="block text-xs text-slate-500">
              Uma folga por semana (segunda a domingo) em qualquer um dos dias marcados. O sistema considera folga o
              primeiro dia sem batida da semana; se ele trabalhar todos os dias, o último dia da semana vira hora extra.
              Para isso, marque todos os dias em que ele pode trabalhar.
            </span>
          </span>
        </label>
      </fieldset>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className="label" htmlFor="start_time">
            Entrada
          </label>
          <input
            id="start_time"
            type="time"
            required
            className="input"
            value={value.start_time}
            onChange={(e) => onChange({ ...value, start_time: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="end_time">
            Saída
          </label>
          <input
            id="end_time"
            type="time"
            required
            className="input"
            value={value.end_time}
            onChange={(e) => onChange({ ...value, end_time: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="lunch_minutes">
            Tempo de almoço (min)
          </label>
          <input
            id="lunch_minutes"
            type="number"
            min={0}
            max={600}
            step={5}
            required
            className="input"
            value={value.lunch_minutes}
            onChange={(e) => onChange({ ...value, lunch_minutes: Number(e.target.value) })}
          />
        </div>
      </div>
      <DayOverrides value={value} onChange={onChange} />
      <p className="text-xs text-slate-500">
        O almoço é livre: o funcionário escolhe quando sair e voltar. Saída menor que a entrada indica turno que
        termina no dia seguinte.
      </p>
    </div>
  );
}

function DayOverrides({ value, onChange }: { value: ScheduleForm; onChange: (value: ScheduleForm) => void }) {
  const days = WEEKDAYS.filter((d) => value.weekdays.includes(d.value));
  if (days.length === 0) return null;
  const setDay = (day: number, times: DayTimes | null) => {
    const overrides = { ...value.overrides };
    if (times) overrides[day] = times;
    else delete overrides[day];
    onChange({ ...value, overrides });
  };
  return (
    <fieldset className="rounded-md border border-slate-200 p-3">
      <legend className="px-1 text-sm font-medium text-slate-700">Algum dia tem horário diferente?</legend>
      <div className="flex flex-wrap gap-2">
        {days
          .filter((d) => !value.overrides[d.value])
          .map((d) => (
            <button
              key={d.value}
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:border-indigo-500"
              onClick={() =>
                setDay(d.value, { start_time: value.start_time, end_time: value.end_time, lunch_minutes: value.lunch_minutes })
              }
            >
              {d.long}: horário diferente
            </button>
          ))}
      </div>
      {days
        .filter((d) => value.overrides[d.value])
        .map((d) => {
          const times = value.overrides[d.value] as DayTimes;
          return (
            <div key={d.value} className="mt-3 grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
              <p className="col-span-2 text-sm font-medium sm:col-span-1">{d.long}</p>
              <label className="text-xs text-slate-600">
                Entrada
                <input
                  type="time"
                  required
                  className="input"
                  aria-label={`Entrada (${d.long})`}
                  value={times.start_time}
                  onChange={(e) => setDay(d.value, { ...times, start_time: e.target.value })}
                />
              </label>
              <label className="text-xs text-slate-600">
                Saída
                <input
                  type="time"
                  required
                  className="input"
                  aria-label={`Saída (${d.long})`}
                  value={times.end_time}
                  onChange={(e) => setDay(d.value, { ...times, end_time: e.target.value })}
                />
              </label>
              <label className="text-xs text-slate-600">
                Almoço (min)
                <input
                  type="number"
                  min={0}
                  max={600}
                  step={5}
                  required
                  className="input"
                  aria-label={`Almoço em minutos (${d.long})`}
                  value={times.lunch_minutes}
                  onChange={(e) => setDay(d.value, { ...times, lunch_minutes: Number(e.target.value) })}
                />
              </label>
              <button
                type="button"
                className="col-span-2 text-left text-xs text-red-700 hover:underline sm:col-span-4"
                onClick={() => setDay(d.value, null)}
              >
                Usar o horário padrão no(a) {d.long.toLowerCase()}
              </button>
            </div>
          );
        })}
    </fieldset>
  );
}
