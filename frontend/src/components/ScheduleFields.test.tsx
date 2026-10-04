import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { DEFAULT_SCHEDULE, ScheduleFields, scheduleToApi, type ScheduleForm } from "./ScheduleFields";

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
});
