import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { DEFAULT_SCHEDULE, ScheduleFields, scheduleFromApi, scheduleToApi, type ScheduleForm } from "./ScheduleFields";

function Harness({ onValue }: { onValue: (v: ScheduleForm) => void }) {
  const [value, setValue] = useState(DEFAULT_SCHEDULE);
  return (
    <ScheduleFields
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

describe("ScheduleFields", () => {
  afterEach(cleanup);

  it("permite digitar dias, horário fixo e tempo de almoço (ex.: João)", async () => {
    let latest = DEFAULT_SCHEDULE;
    render(<Harness onValue={(v) => (latest = v)} />);
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Sábado"));
    await user.click(screen.getByLabelText("Segunda"));
    const end = screen.getByLabelText("Saída");
    await user.clear(end);
    await user.type(end, "16:00");
    const lunch = screen.getByLabelText("Tempo de almoço (min)");
    await user.clear(lunch);
    await user.type(lunch, "30");

    expect(scheduleToApi(latest)).toEqual({
      weekdays: [1, 2, 3, 4, 5],
      start_time: "08:00",
      end_time: "16:00",
      lunch_minutes: 30,
      weekly_day_off: false,
      double_off_week: null,
    });
  });

  it("permite marcar a folga semanal em qualquer dia", async () => {
    let latest = DEFAULT_SCHEDULE;
    render(<Harness onValue={(v) => (latest = v)} />);
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Sábado"));
    await user.click(screen.getByLabelText("Domingo"));
    await user.click(screen.getByRole("checkbox", { name: /Folga semanal em qualquer dia/ }));

    expect(scheduleToApi(latest)).toMatchObject({ weekdays: [0, 1, 2, 3, 4, 5, 6], weekly_day_off: true });
  });

  it("permite um horário diferente no sábado (ex.: Grazi 07:30–14:30)", async () => {
    let latest = DEFAULT_SCHEDULE;
    render(<Harness onValue={(v) => (latest = v)} />);
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Sábado"));
    await user.click(screen.getByRole("button", { name: "Sábado: horário diferente" }));
    const start = screen.getByLabelText("Entrada (Sábado)");
    await user.clear(start);
    await user.type(start, "07:30");
    const end = screen.getByLabelText("Saída (Sábado)");
    await user.clear(end);
    await user.type(end, "14:30");
    const lunch = screen.getByLabelText("Almoço em minutos (Sábado)");
    await user.clear(lunch);
    await user.type(lunch, "0");

    const body = scheduleToApi(latest) as { days: { weekday: number; start_time: string; end_time: string; lunch_minutes: number }[] };
    expect(body.days).toHaveLength(6);
    expect(body.days[0]).toEqual({ weekday: 0, start_time: "08:00", end_time: "17:00", lunch_minutes: 60 });
    expect(body.days[5]).toEqual({ weekday: 5, start_time: "07:30", end_time: "14:30", lunch_minutes: 0 });

    await user.click(screen.getByRole("button", { name: /Usar o horário padrão/ }));
    expect(scheduleToApi(latest)).toMatchObject({ weekdays: [0, 1, 2, 3, 4, 5], start_time: "08:00" });
  });

  it("monta o formulário a partir do horário salvo, com o sábado como exceção", () => {
    const day = (weekday: number, start: string, end: string, lunch: number) => ({
      weekday,
      start_time: `${start}:00`,
      end_time: `${end}:00`,
      lunch_minutes: lunch,
      planned_minutes: 0,
    });
    const form = scheduleFromApi({
      id: 1,
      valid_from: "2026-11-01",
      valid_to: null,
      weekly_day_off: false,
      created_at: "2026-11-01T10:00:00-03:00",
      days: [0, 1, 2, 3, 4].map((d) => day(d, "08:00", "16:00", 60)).concat([day(5, "07:30", "14:30", 0)]),
    });
    expect(form).toMatchObject({ weekdays: [0, 1, 2, 3, 4, 5], start_time: "08:00", end_time: "16:00", lunch_minutes: 60 });
    expect(form.overrides).toEqual({ 5: { start_time: "07:30", end_time: "14:30", lunch_minutes: 0 } });
  });

  it("alterna semanas com 2 e 1 folgas só com a folga semanal marcada", async () => {
    let latest = DEFAULT_SCHEDULE;
    render(<Harness onValue={(v) => (latest = v)} />);
    const user = userEvent.setup();

    expect(screen.queryByLabelText(/Alternar: uma semana com 2 folgas/)).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: /Folga semanal em qualquer dia/ }));
    await user.click(screen.getByLabelText(/Alternar: uma semana com 2 folgas/));
    fireEvent.change(screen.getByLabelText(/Uma semana com 2 folgas/), { target: { value: "2026-11-04" } });

    expect(scheduleToApi(latest)).toMatchObject({ weekly_day_off: true, double_off_week: "2026-11-04" });
    expect(scheduleToApi({ ...latest, weekly_day_off: false })).toMatchObject({ double_off_week: null });
  });
});
