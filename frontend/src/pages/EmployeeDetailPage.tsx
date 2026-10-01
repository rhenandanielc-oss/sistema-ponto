import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { api, type Schemas } from "../api/client";
import { DEFAULT_SCHEDULE, ScheduleFields, scheduleToApi, type ScheduleForm } from "../components/ScheduleFields";
import { Badge, ErrorMessage, Loading, Modal, PageHeader } from "../components/ui";
import { WEEKDAYS, formatDate, formatDateTime, formatMinutes, shortTime } from "../lib/format";
import { toIsoDate } from "../lib/period";

type Employee = Schemas["EmployeeDetail"];
type Schedule = Schemas["ScheduleOut"];

const ACTION_LABELS: Record<string, string> = {
  "employee.create": "Cadastro",
  "employee.update": "Alteração de dados",
  "employee.activate": "Ativação",
  "employee.deactivate": "Desativação",
  "employee.schedule_create": "Novo horário",
  "hour_bank.entry_create": "Lançamento no banco de horas",
};

export function EmployeeDetailPage() {
  const id = Number(useParams().id);
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [changingSchedule, setChangingSchedule] = useState(false);

  const employee = useQuery({ queryKey: ["employee", id], queryFn: () => api<Employee>(`/employees/${id}`) });
  const schedules = useQuery({
    queryKey: ["employee", id, "schedules"],
    queryFn: () => api<Schedule[]>(`/employees/${id}/schedules`),
  });
  const history = useQuery({
    queryKey: ["employee", id, "history"],
    queryFn: () => api<Schemas["Page_AuditEntryOut_"]>(`/employees/${id}/history`, { query: { page_size: 50 } }),
  });

  const toggleStatus = useMutation({
    mutationFn: (active: boolean) =>
      api<Employee>(`/employees/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["employee", id] }),
  });

  if (employee.isLoading) return <Loading />;
  if (employee.error || !employee.data) return <ErrorMessage error={employee.error} />;
  const e = employee.data;
  const active = e.status === "ACTIVE";

  return (
    <>
      <PageHeader
        title={e.name}
        actions={
          <>
            <Link className="btn-secondary" to={`/banco-de-horas/${e.id}`}>
              Banco de horas
            </Link>
            <button type="button" className="btn-secondary" onClick={() => setEditing(true)}>
              Editar dados
            </button>
            <button
              type="button"
              className={active ? "btn-danger" : "btn-primary"}
              disabled={toggleStatus.isPending}
              onClick={() => {
                if (!active || window.confirm(`Desativar ${e.name}? Ele deixará de bater ponto.`)) {
                  toggleStatus.mutate(!active);
                }
              }}
            >
              {active ? "Desativar" : "Ativar"}
            </button>
          </>
        }
      />
      <ErrorMessage error={toggleStatus.error} />
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card space-y-2 text-sm">
          <h2 className="mb-2 font-semibold text-slate-800">Dados</h2>
          <p>
            <span className="text-slate-500">Situação: </span>
            {active ? <Badge tone="green">Ativo</Badge> : <Badge tone="slate">Inativo</Badge>}
          </p>
          <p>
            <span className="text-slate-500">Matrícula: </span>
            {e.registration_number}
          </p>
          <p>
            <span className="text-slate-500">CPF: </span>
            {e.cpf ?? "—"}
          </p>
          <p>
            <span className="text-slate-500">Admissão: </span>
            {formatDate(e.hire_date)}
          </p>
          <p>
            <span className="text-slate-500">Desligamento: </span>
            {e.termination_date ? formatDate(e.termination_date) : "—"}
          </p>
          <p className="pt-2 text-xs text-slate-500">Rosto para o terminal: disponível na Fase 5.</p>
        </section>

        <section className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">Horário fixo</h2>
            <button type="button" className="btn-secondary" onClick={() => setChangingSchedule(true)}>
              Alterar horário
            </button>
          </div>
          {e.current_schedule ? <ScheduleTable schedule={e.current_schedule} /> : <p>Sem horário.</p>}
          {schedules.data && schedules.data.length > 1 && (
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-slate-600">Horários anteriores</summary>
              <ul className="mt-2 space-y-1">
                {schedules.data.map((s) => (
                  <li key={s.id}>
                    {formatDate(s.valid_from)} até {s.valid_to ? formatDate(s.valid_to) : "hoje"} —{" "}
                    {s.days.map((d) => WEEKDAYS[d.weekday]?.short).join(", ")}{" "}
                    {s.days[0] && `${shortTime(s.days[0].start_time)}–${shortTime(s.days[0].end_time)}`}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      </div>

      <section className="card mt-6">
        <h2 className="mb-3 font-semibold text-slate-800">Histórico de alterações</h2>
        {history.data && (
          <ul className="divide-y divide-slate-100 text-sm">
            {history.data.items.map((h) => (
              <li key={h.id} className="py-2">
                <span className="text-slate-500">{formatDateTime(h.occurred_at)}</span> —{" "}
                <span className="font-medium">{ACTION_LABELS[h.action] ?? h.action}</span>
                <ChangeSummary before={h.before} after={h.after} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {editing && <EditEmployeeModal employee={e} onClose={() => setEditing(false)} />}
      {changingSchedule && <NewScheduleModal employee={e} onClose={() => setChangingSchedule(false)} />}
    </>
  );
}

function ScheduleTable({ schedule }: { schedule: Schedule }) {
  return (
    <>
      <p className="mb-2 text-sm text-slate-500">
        Vigente desde {formatDate(schedule.valid_from)}
        {schedule.valid_to ? ` até ${formatDate(schedule.valid_to)}` : ""}
      </p>
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Dia</th>
              <th>Entrada</th>
              <th>Saída</th>
              <th>Almoço</th>
              <th>Carga do dia</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {schedule.days.map((d) => (
              <tr key={d.weekday}>
                <td>{WEEKDAYS[d.weekday]?.long}</td>
                <td>{shortTime(d.start_time)}</td>
                <td>{shortTime(d.end_time)}</td>
                <td>{d.lunch_minutes} min</td>
                <td>{formatMinutes(d.planned_minutes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ChangeSummary({
  before,
  after,
}: {
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}) {
  if (!before || !after) return null;
  const changed = Object.keys(after).filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]));
  if (changed.length === 0) return null;
  return (
    <span className="text-slate-600">
      {" "}
      ({changed.map((k) => `${k}: ${String(before[k] ?? "—")} → ${String(after[k] ?? "—")}`).join("; ")})
    </span>
  );
}

function EditEmployeeModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: employee.name,
    registration_number: employee.registration_number,
    cpf: employee.cpf ?? "",
    hire_date: employee.hire_date,
    termination_date: employee.termination_date ?? "",
  });
  const mutation = useMutation({
    mutationFn: () =>
      api<Employee>(`/employees/${employee.id}`, {
        method: "PATCH",
        body: { ...form, cpf: form.cpf || null, termination_date: form.termination_date || null },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employee", employee.id] });
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
      onClose();
    },
  });
  const field = (key: keyof typeof form, label: string, type = "text", required = true) => (
    <div>
      <label className="label" htmlFor={`edit-${key}`}>
        {label}
      </label>
      <input
        id={`edit-${key}`}
        type={type}
        required={required}
        className="input"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      />
    </div>
  );
  return (
    <Modal title="Editar dados" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <ErrorMessage error={mutation.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          {field("name", "Nome")}
          {field("registration_number", "Matrícula")}
          {field("cpf", "CPF (opcional)", "text", false)}
          {field("hire_date", "Admissão", "date")}
          {field("termination_date", "Desligamento (opcional)", "date", false)}
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={mutation.isPending}>
            Salvar
          </button>
        </div>
      </form>
    </Modal>
  );
}

function NewScheduleModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const queryClient = useQueryClient();
  const current = employee.current_schedule;
  const first = current?.days[0];
  const [validFrom, setValidFrom] = useState(() => toIsoDate(new Date()));
  const [schedule, setSchedule] = useState<ScheduleForm>(
    current && first
      ? {
          weekdays: current.days.map((d) => d.weekday),
          start_time: shortTime(first.start_time),
          end_time: shortTime(first.end_time),
          lunch_minutes: first.lunch_minutes,
        }
      : DEFAULT_SCHEDULE,
  );
  const mutation = useMutation({
    mutationFn: () =>
      api<Schedule>(`/employees/${employee.id}/schedules`, {
        method: "POST",
        body: { valid_from: validFrom, ...scheduleToApi(schedule) },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employee", employee.id] });
      onClose();
    },
  });
  return (
    <Modal title="Alterar horário" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <ErrorMessage error={mutation.error} />
        <div className="max-w-xs">
          <label className="label" htmlFor="valid_from">
            Vale a partir de
          </label>
          <input
            id="valid_from"
            type="date"
            required
            className="input"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-500">Dias anteriores continuam calculados com o horário antigo.</p>
        </div>
        <ScheduleFields value={schedule} onChange={setSchedule} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={mutation.isPending}>
            Salvar horário
          </button>
        </div>
      </form>
    </Modal>
  );
}
