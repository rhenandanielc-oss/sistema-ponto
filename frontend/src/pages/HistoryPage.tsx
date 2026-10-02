import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type Schemas } from "../api/client";
import { EmployeeSelect } from "../components/EmployeeSelect";
import { PeriodPicker } from "../components/PeriodPicker";
import { Badge, Empty, ErrorMessage, Loading, Modal, PageHeader, Pagination } from "../components/ui";
import { RECORD_TYPE_LABELS, formatDate, formatDateTime, formatTime, weekdayOf } from "../lib/format";
import { presetPeriod, toIsoDate, type PeriodPreset } from "../lib/period";

type Record_ = Schemas["TimeRecordOut"];
const PAGE_SIZE = 50;

export function HistoryPage() {
  const [employeeId, setEmployeeId] = useState<number | null>(null);
  const [preset, setPreset] = useState<PeriodPreset>("week");
  const [period, setPeriod] = useState(() => presetPeriod("week"));
  const [type, setType] = useState("");
  const [includeVoided, setIncludeVoided] = useState(false);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Record_ | null>(null);
  const [adding, setAdding] = useState(false);

  const query = useQuery({
    queryKey: ["time-records", { employeeId, period, type, includeVoided, page }],
    queryFn: () =>
      api<Schemas["Page_TimeRecordOut_"]>("/time-records", {
        query: {
          employee_id: employeeId,
          date_from: period.from,
          date_to: period.to,
          type,
          include_voided: includeVoided,
          page,
          page_size: PAGE_SIZE,
        },
      }),
  });

  return (
    <>
      <PageHeader
        title="Histórico de batidas"
        actions={
          <button type="button" className="btn-primary" onClick={() => setAdding(true)}>
            Incluir batida esquecida
          </button>
        }
      />
      <div className="card">
        <div className="mb-4 grid gap-3 lg:grid-cols-4">
          <EmployeeSelect value={employeeId} allowAll onChange={(id) => {
              setEmployeeId(id);
              setPage(1);
            }} />
          <select className="input" aria-label="Tipo" value={type} onChange={(e) => {
              setType(e.target.value);
              setPage(1);
            }}>
            <option value="">Todos os tipos</option>
            {Object.entries(RECORD_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600 lg:col-span-2">
            <input type="checkbox" checked={includeVoided} onChange={(e) => setIncludeVoided(e.target.checked)} />
            Mostrar batidas anuladas
          </label>
        </div>
        <div className="mb-4">
          <PeriodPicker
            preset={preset}
            period={period}
            onChange={(p, value) => {
              setPreset(p);
              setPeriod(value);
              setPage(1);
            }}
          />
        </div>
        <ErrorMessage error={query.error} />
        {query.isLoading ? (
          <Loading />
        ) : query.data && query.data.items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Funcionário</th>
                    <th>Tipo</th>
                    <th>Horário</th>
                    <th>Origem</th>
                    <th />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {query.data.items.map((r) => (
                    <tr key={r.id} className={r.voided_at ? "text-slate-400 line-through" : ""}>
                      <td>
                        {weekdayOf(r.workday_date)} {formatDate(r.workday_date)}
                      </td>
                      <td>{r.employee_name}</td>
                      <td>{RECORD_TYPE_LABELS[r.type]}</td>
                      <td className="tabular-nums">
                        {formatTime(r.recorded_at)}
                        {r.recorded_at.slice(0, 10) !== r.workday_date && (
                          <span className="ml-1 text-xs text-slate-500">({formatDate(r.recorded_at.slice(0, 10))})</span>
                        )}
                      </td>
                      <td>
                        {r.source === "KIOSK" ? <Badge tone="indigo">Terminal</Badge> : <Badge tone="amber">Ajuste</Badge>}
                        {r.voided_at && (
                          <span className="ml-1">
                            <Badge tone="red">Anulada</Badge>
                          </span>
                        )}
                      </td>
                      <td>
                        <button type="button" className="text-sm text-indigo-700 hover:underline" onClick={() => setSelected(r)}>
                          Detalhes
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
          </>
        ) : (
          <Empty>Nenhuma batida no período.</Empty>
        )}
      </div>
      {selected && <RecordDetailModal recordId={selected.id} onClose={() => setSelected(null)} />}
      {adding && <AddRecordModal defaultEmployee={employeeId} onClose={() => setAdding(false)} />}
    </>
  );
}

function RecordDetailModal({ recordId, onClose }: { recordId: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const detail = useQuery({
    queryKey: ["time-record", recordId],
    queryFn: () => api<Schemas["TimeRecordDetail"]>(`/time-records/${recordId}`),
  });
  const voiding = useMutation({
    mutationFn: () =>
      api("/time-records/adjustments", { method: "POST", body: { kind: "VOID", record_id: recordId, reason } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["time-records"] });
      void queryClient.invalidateQueries({ queryKey: ["time-record", recordId] });
      setReason("");
    },
  });
  const r = detail.data;
  return (
    <Modal title="Detalhes da batida" onClose={onClose}>
      {!r ? (
        <Loading />
      ) : (
        <div className="space-y-4 text-sm">
          <dl className="grid grid-cols-2 gap-2">
            <dt className="text-slate-500">Funcionário</dt>
            <dd>{r.employee_name}</dd>
            <dt className="text-slate-500">Tipo</dt>
            <dd>{RECORD_TYPE_LABELS[r.type]}</dd>
            <dt className="text-slate-500">Horário oficial</dt>
            <dd>{formatDateTime(r.recorded_at)}</dd>
            <dt className="text-slate-500">Dia de jornada</dt>
            <dd>{formatDate(r.workday_date)}</dd>
            <dt className="text-slate-500">Origem</dt>
            <dd>{r.source === "KIOSK" ? `Terminal${r.device_id ? ` #${r.device_id}` : ""}` : "Ajuste do administrador"}</dd>
            {r.face_match_score !== null && (
              <>
                <dt className="text-slate-500">Reconhecimento</dt>
                <dd>{(r.face_match_score * 100).toFixed(0)}%</dd>
              </>
            )}
            <dt className="text-slate-500">Registrada em</dt>
            <dd>{formatDateTime(r.created_at)}</dd>
          </dl>
          {r.adjustments.length > 0 && (
            <div>
              <h3 className="mb-1 font-semibold">Ajustes</h3>
              <ul className="space-y-1">
                {r.adjustments.map((a) => (
                  <li key={a.id}>
                    {a.kind === "ADD" ? "Incluída" : "Anulada"} em {formatDateTime(a.created_at)} — “{a.reason}”
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!r.voided_at && (
            <form
              className="space-y-2 border-t border-slate-200 pt-4"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                voiding.mutate();
              }}
            >
              <h3 className="font-semibold">Anular batida</h3>
              <p className="text-slate-500">A batida continua no histórico, marcada como anulada.</p>
              <ErrorMessage error={voiding.error} />
              <textarea
                className="input"
                aria-label="Justificativa"
                placeholder="Justificativa (mínimo 10 caracteres)"
                minLength={10}
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <button type="submit" className="btn-danger" disabled={voiding.isPending}>
                Anular
              </button>
            </form>
          )}
        </div>
      )}
    </Modal>
  );
}

function AddRecordModal({ defaultEmployee, onClose }: { defaultEmployee: number | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [employeeId, setEmployeeId] = useState<number | null>(defaultEmployee);
  const [type, setType] = useState("EXIT");
  const [date, setDate] = useState(() => toIsoDate(new Date()));
  const [time, setTime] = useState("");
  const [workday, setWorkday] = useState("");
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api("/time-records/adjustments", {
        method: "POST",
        body: {
          kind: "ADD",
          employee_id: employeeId,
          type,
          // Data e hora no relógio da empresa; o backend aplica o fuso.
          recorded_at: `${date}T${time}`,
          workday_date: workday || null,
          reason,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["time-records"] });
      void queryClient.invalidateQueries({ queryKey: ["hour-bank"] });
      onClose();
    },
  });
  return (
    <Modal title="Incluir batida esquecida" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <ErrorMessage error={mutation.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="add-employee">
              Funcionário
            </label>
            <EmployeeSelect id="add-employee" value={employeeId} onChange={setEmployeeId} />
          </div>
          <div>
            <label className="label" htmlFor="add-type">
              Tipo
            </label>
            <select id="add-type" className="input" value={type} onChange={(e) => setType(e.target.value)}>
              {Object.entries(RECORD_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label" htmlFor="add-date">
                Data
              </label>
              <input id="add-date" type="date" required className="input" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="add-time">
                Hora
              </label>
              <input id="add-time" type="time" required className="input" value={time} onChange={(e) => setTime(e.target.value)} />
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="add-workday">
              Dia de jornada (só para turno que passa da meia-noite)
            </label>
            <input id="add-workday" type="date" className="input" value={workday} onChange={(e) => setWorkday(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="add-reason">
              Justificativa
            </label>
            <textarea
              id="add-reason"
              className="input"
              minLength={10}
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={mutation.isPending || employeeId === null}>
            Incluir
          </button>
        </div>
      </form>
    </Modal>
  );
}
