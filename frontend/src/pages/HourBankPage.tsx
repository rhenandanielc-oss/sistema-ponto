import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, type Schemas } from "../api/client";
import { PeriodPicker } from "../components/PeriodPicker";
import { Balance, Empty, ErrorMessage, Loading, PageHeader, Pagination } from "../components/ui";
import { formatMinutes } from "../lib/format";
import { presetPeriod, type PeriodPreset } from "../lib/period";

const PAGE_SIZE = 50;

export function HourBankPage() {
  const [preset, setPreset] = useState<PeriodPreset>("month");
  const [period, setPeriod] = useState(() => presetPeriod("month"));
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["hour-bank", "summary", { period, q, page }],
    queryFn: () =>
      api<Schemas["Page_HourBankSummaryItem_"]>("/hour-bank/summary", {
        query: { date_from: period.from, date_to: period.to, q, status: "ACTIVE", page, page_size: PAGE_SIZE },
      }),
  });

  return (
    <>
      <PageHeader title="Banco de horas" />
      <div className="card">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <PeriodPicker
            preset={preset}
            period={period}
            onChange={(p, value) => {
              setPreset(p);
              setPeriod(value);
              setPage(1);
            }}
          />
          <input
            className="input max-w-xs"
            placeholder="Buscar funcionário"
            aria-label="Buscar funcionário"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
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
                    <th>Funcionário</th>
                    <th>Saldo anterior</th>
                    <th>Previsto</th>
                    <th>Trabalhado</th>
                    <th>Extras</th>
                    <th>Faltantes</th>
                    <th>Faltas</th>
                    <th>Saldo final</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {query.data.items.map((row) => (
                    <tr key={row.employee_id} className="hover:bg-slate-50">
                      <td>
                        <Link className="font-medium text-indigo-700 hover:underline" to={`/banco-de-horas/${row.employee_id}`}>
                          {row.name}
                        </Link>
                        {row.incomplete_days > 0 && (
                          <span className="ml-2 text-xs text-amber-700">{row.incomplete_days} dia(s) incompleto(s)</span>
                        )}
                      </td>
                      <td>
                        <Balance minutes={row.opening_balance_minutes} />
                      </td>
                      <td className="tabular-nums">{formatMinutes(row.planned_minutes)}</td>
                      <td className="tabular-nums">{formatMinutes(row.worked_minutes)}</td>
                      <td className="tabular-nums text-green-700">{formatMinutes(row.overtime_minutes)}</td>
                      <td className="tabular-nums text-red-700">{formatMinutes(row.missing_minutes)}</td>
                      <td>{row.absences}</td>
                      <td>
                        <Balance minutes={row.closing_balance_minutes} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
          </>
        ) : (
          <Empty>Nenhum funcionário ativo.</Empty>
        )}
      </div>
    </>
  );
}
