import { WEEKDAYS } from "../lib/format";

/** Valores do formulário de horário fixo, como o administrador digita. */
export interface ScheduleForm {
  weekdays: number[];
  start_time: string;
  end_time: string;
  lunch_minutes: number;
  weekly_day_off: boolean;
}

export const DEFAULT_SCHEDULE: ScheduleForm = {
  weekdays: [0, 1, 2, 3, 4],
  start_time: "08:00",
  end_time: "17:00",
  lunch_minutes: 60,
  weekly_day_off: false,
};

/** Corpo esperado pela API na forma simples (o backend valida e calcula a carga). */
export function scheduleToApi(form: ScheduleForm) {
  return {
    weekdays: [...form.weekdays].sort((a, b) => a - b),
    start_time: form.start_time,
    end_time: form.end_time,
    lunch_minutes: form.lunch_minutes,
    weekly_day_off: form.weekly_day_off,
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
      <p className="text-xs text-slate-500">
        O almoço é livre: o funcionário escolhe quando sair e voltar. Saída menor que a entrada indica turno que
        termina no dia seguinte.
      </p>
    </div>
  );
}
