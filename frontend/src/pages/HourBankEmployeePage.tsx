import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { api, type Schemas } from "../api/client";
import { PeriodPicker } from "../components/PeriodPicker";
import { Badge, Balance, ErrorMessage, Loading, Modal, PageHeader } from "../components/ui";
import {
  DAY_STATUS_LABELS,
  DAY_TYPE_LABELS,
  FLAG_LABELS,
  RECORD_TYPE_LABELS,
  formatDate,
  formatMinutes,
  formatTime,
  weekdayOf,
} from "../lib/format";
import { presetPeriod, toIsoDate, type PeriodPreset } from "../lib/period";

type Day = Schemas["DayOut"];

const ENTRY_KINDS: Record<string, string> = {
  OPENING_BALANCE: "Saldo inicial",
  COMPENSATION: "Folga compensada",
  PAYOUT: "Pagamento de horas",
  CORRECTION: "Correção",
};

function statusTone(day: Day): "green" | "red" | "amber" | "slate" | "indigo" {
  if (day.status === "ABSENT") return "red";
  if (day.status === "INCOMPLETE") return "amber";
  if (day.status === "IN_PROGRESS") return "indigo";
  if (day.status === "OK") return "green";
  return "slate";
}

export function HourBankEmployeePage() {
  const id = Number(useParams().id);
  const [preset, setPreset] = useState<PeriodPreset>("month");
  const [period, setPeriod] = useState(() => presetPeriod("month"));
  const [addingEntry, setAddingEntry] = useState(false);

  const employee = useQuery({
    queryKey: ["employee", id],
    queryFn: () => api<Schemas["EmployeeDetail"]>(`/employees/${id}`),
  });
  const bank = useQuery({
    queryKey: ["hour-bank", id, period],
    queryFn: () =>
      api<Schemas["HourBankOut"]>(`/employees/${id}/hour-bank`, {
        query: { date_from: period.from, date_to: period.to },
      }),
  });

  return (
    <>
      <PageHeader
        title={`Banco de horas${employee.data ? ` — ${employee.data.name}` : ""}`}
        actions={
          <>
            <Link className="btn-secondary" to={`/funcionarios/${id}`}>
              Cadastro
            </Link>
            <button type="button" className="btn-primary" onClick={() => setAddingEntry(true)}>
              Lançamento manual
            </button>
          </>
        }
      />
      <div className="mb-4">
        <PeriodPicker
          preset={preset}
          period={period}
          onChange={(p, value) => {
            setPreset(p);
            setPeriod(value);
          }}
        />
      </div>
      <ErrorMessage error={bank.error} />
      {bank.isLoading || !bank.data ? (
        <Loading />
      ) : (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label="Saldo anterior" value={<Balance minutes={bank.data.opening_balance_minutes} />} />
            <Stat label="Horas extras" value={formatMinutes(bank.data.totals.overtime_minutes)} />
            <Stat label="Horas faltantes" value={formatMinutes(bank.data.totals.missing_minutes)} />
            <Stat label="Lançamentos" value={<Balance minutes={bank.data.entries_minutes} />} />
            <Stat label="Saldo final" value={<Balance minutes={bank.data.closing_balance_minutes} />} />
          </div>
          <div className="card">
            <h2 className="mb-3 font-semibold text-slate-800">Detalhamento diário</h2>
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Batidas</th>
                    <th>Previsto</th>
                    <th>Trabalhado</th>
                    <th>Almoço</th>
                    <th>Atraso</th>
                    <th>Saída antec.</th>
                    <th>Saldo</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {bank.data.days.map((d) => (
                    <tr key={d.date} className={d.day_type !== "WORKDAY" ? "bg-slate-50" : ""}>
                      <td>
                        {weekdayOf(d.date)} {formatDate(d.date)}
                        {d.day_type !== "WORKDAY" && (
                          <span className="ml-1 text-xs text-slate-500">{DAY_TYPE_LABELS[d.day_type]}</span>
                        )}
                      </td>
                      <td className="text-xs tabular-nums">
                        {d.punches.map((p) => (
                          <span key={p.type} className="mr-2" title={RECORD_TYPE_LABELS[p.type]}>
                            {formatTime(p.at)}
                          </span>
                        ))}
                      </td>
                      <td className="tabular-nums">{d.planned_minutes ? formatMinutes(d.planned_minutes) : "—"}</td>
                      <td className="tabular-nums">{d.worked_minutes ? formatMinutes(d.worked_minutes) : "—"}</td>
                      <td className="tabular-nums">{d.break_minutes ? `${d.break_minutes} min` : "—"}</td>
                      <td className="tabular-nums">{d.late_minutes ? `${d.late_minutes} min` : "—"}</td>
                      <td className="tabular-nums">{d.early_leave_minutes ? `${d.early_leave_minutes} min` : "—"}</td>
                      <td>{d.counts_for_bank ? <Balance minutes={d.balance_minutes} /> : "—"}</td>
                      <td className="space-x-1">
                        {d.status !== "NONE" && <Badge tone={statusTone(d)}>{DAY_STATUS_LABELS[d.status]}</Badge>}
                        {d.flags.map((f) => (
                          <Badge key={f} tone="amber">
                            {FLAG_LABELS[f] ?? f}
                          </Badge>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {bank.data.entries.length > 0 && (
            <div className="card mt-6">
              <h2 className="mb-3 font-semibold text-slate-800">Lançamentos no período</h2>
              <ul className="divide-y divide-slate-100 text-sm">
                {bank.data.entries.map((e) => (
                  <li key={e.id} className="flex flex-wrap justify-between gap-2 py-2">
                    <span>
                      {formatDate(e.entry_date)} — {ENTRY_KINDS[e.kind] ?? e.kind}: {e.reason}
                    </span>
                    <Balance minutes={e.minutes} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {addingEntry && <EntryModal employeeId={id} onClose={() => setAddingEntry(false)} />}
    </>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function EntryModal({ employeeId, onClose }: { employeeId: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [date, setDate] = useState(() => toIsoDate(new Date()));
  const [kind, setKind] = useState("CORRECTION");
  const [direction, setDirection] = useState<1 | -1>(1);
  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(0);
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api(`/employees/${employeeId}/hour-bank/entries`, {
        method: "POST",
        body: { entry_date: date, kind, minutes: direction * (hours * 60 + minutes), reason },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hour-bank"] });
      onClose();
    },
  });
  return (
    <Modal title="Lançamento manual no banco de horas" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <ErrorMessage error={mutation.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="entry-kind">
              Tipo
            </label>
            <select id="entry-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.entries(ENTRY_KINDS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="entry-date">
              Data
            </label>
            <input id="entry-date" type="date" required className="input" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="entry-direction">
              Crédito ou débito
            </label>
            <select
              id="entry-direction"
              className="input"
              value={direction}
              onChange={(e) => setDirection(Number(e.target.value) as 1 | -1)}
            >
              <option value={1}>Crédito (+)</option>
              <option value={-1}>Débito (−)</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label" htmlFor="entry-hours">
                Horas
              </label>
              <input id="entry-hours" type="number" min={0} className="input" value={hours} onChange={(e) => setHours(Number(e.target.value))} />
            </div>
            <div>
              <label className="label" htmlFor="entry-minutes">
                Minutos
              </label>
              <input
                id="entry-minutes"
                type="number"
                min={0}
                max={59}
                className="input"
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="entry-reason">
              Justificativa
            </label>
            <textarea id="entry-reason" className="input" minLength={10} required value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={mutation.isPending}>
            Lançar
          </button>
        </div>
      </form>
    </Modal>
  );
}
