import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, type Schemas } from "../api/client";
import { Badge, Empty, ErrorMessage, Loading, PageHeader, Pagination } from "../components/ui";
import { formatDate, formatDecimalHours, formatMinutes } from "../lib/format";

const PAGE_SIZE = 50;

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Horas de cada funcionário no ciclo pago no mês escolhido. O sistema só calcula as horas;
 * o administrador multiplica pelo valor da hora (pedido do responsável).
 */
export function PayrollPage() {
  const [month, setMonth] = useState(currentMonth);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["payroll", "summary", { month, q, page }],
    queryFn: () =>
      api<Schemas["Page_PayrollOut_"]>("/payroll", {
        query: { payment_month: month, q, page, page_size: PAGE_SIZE },
      }),
    enabled: /^\d{4}-\d{2}$/.test(month),
  });

  return (
    <>
      <PageHeader title="Pagamento" />
      <div className="card">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <label className="label" htmlFor="payment-month">
              Pagamentos do mês
            </label>
            <input
              id="payment-month"
              type="month"
              className="input w-auto"
              value={month}
              onChange={(e) => {
                setMonth(e.target.value);
                setPage(1);
              }}
            />
          </div>
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
        <p className="mb-4 text-sm text-slate-500">
          Cada funcionário tem o seu ciclo: do dia seguinte ao pagamento anterior até o dia do pagamento.{" "}
          <strong>Horas a pagar = horas fixas (salário) + extras − faltantes.</strong> Multiplique as horas a pagar
          pelo valor da hora (as horas estão em decimal: 7h30 = 7,50).
        </p>
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
                    <th>Pagamento</th>
                    <th>Período</th>
                    <th>Horas fixas</th>
                    <th>+ Extras</th>
                    <th>− Faltantes</th>
                    <th>= Horas a pagar</th>
                    <th>Trabalhadas</th>
                    <th>Faltas</th>
                    <th />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {query.data.items.map((p) => (
                    <tr key={p.employee_id} className="hover:bg-slate-50">
                      <td className="font-medium">{p.name}</td>
                      <td>
                        {formatDate(p.payment_date)}{" "}
                        {!p.closed && <Badge tone="indigo">em andamento</Badge>}
                      </td>
                      <td className="text-slate-600">
                        {formatDate(p.period_start)} a {formatDate(p.period_end)}
                      </td>
                      <td className="tabular-nums">{formatDecimalHours(p.planned_hours)} h</td>
                      <td className="tabular-nums text-green-700">{formatDecimalHours(p.overtime_hours)} h</td>
                      <td className="tabular-nums text-red-700">{formatDecimalHours(p.missing_hours)} h</td>
                      <td className="tabular-nums" data-testid="payable">
                        <span className="font-semibold">{formatDecimalHours(p.payable_hours)} h</span>
                        <span className="ml-1 text-xs text-slate-500">({formatMinutes(p.payable_minutes)})</span>
                      </td>
                      <td className="tabular-nums text-slate-600">{formatDecimalHours(p.worked_hours)} h</td>
                      <td>{p.absences}</td>
                      <td className="space-x-2">
                        {p.incomplete_days > 0 && (
                          <Badge tone="amber">
                            {p.incomplete_days} dia(s) incompleto(s)
                          </Badge>
                        )}
                        <Link
                          className="text-sm text-indigo-700 hover:underline"
                          to={`/banco-de-horas/${p.employee_id}?de=${p.period_start}&ate=${p.period_end}`}
                        >
                          Detalhe
                        </Link>
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
