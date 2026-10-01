import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { api, type Schemas } from "../api/client";
import { DEFAULT_SCHEDULE, ScheduleFields, scheduleToApi, type ScheduleForm } from "../components/ScheduleFields";
import { Badge, Empty, ErrorMessage, Loading, Modal, PageHeader, Pagination } from "../components/ui";
import { formatDate } from "../lib/format";
import { toIsoDate } from "../lib/period";

const PAGE_SIZE = 20;

export function EmployeesPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"" | "ACTIVE" | "INACTIVE">("ACTIVE");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);

  const query = useQuery({
    queryKey: ["employees", { q, status, page }],
    queryFn: () =>
      api<Schemas["Page_EmployeeOut_"]>("/employees", {
        query: { q, status, page, page_size: PAGE_SIZE, sort: "name" },
      }),
  });

  return (
    <>
      <PageHeader
        title="Funcionários"
        actions={
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            Novo funcionário
          </button>
        }
      />
      <div className="card">
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <input
            className="input sm:col-span-2"
            placeholder="Buscar por nome ou matrícula"
            aria-label="Buscar"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <select
            className="input"
            aria-label="Situação"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as typeof status);
              setPage(1);
            }}
          >
            <option value="ACTIVE">Ativos</option>
            <option value="INACTIVE">Inativos</option>
            <option value="">Todos</option>
          </select>
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
                    <th>Nome</th>
                    <th>Matrícula</th>
                    <th>Admissão</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {query.data.items.map((e) => (
                    <tr key={e.id} className="hover:bg-slate-50">
                      <td>
                        <Link className="font-medium text-indigo-700 hover:underline" to={`/funcionarios/${e.id}`}>
                          {e.name}
                        </Link>
                      </td>
                      <td>{e.registration_number}</td>
                      <td>{formatDate(e.hire_date)}</td>
                      <td>
                        {e.status === "ACTIVE" ? <Badge tone="green">Ativo</Badge> : <Badge tone="slate">Inativo</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
          </>
        ) : (
          <Empty>Nenhum funcionário encontrado.</Empty>
        )}
      </div>
      {creating && <CreateEmployeeModal onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateEmployeeModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [registration, setRegistration] = useState("");
  const [cpf, setCpf] = useState("");
  const [hireDate, setHireDate] = useState(() => toIsoDate(new Date()));
  const [schedule, setSchedule] = useState<ScheduleForm>(DEFAULT_SCHEDULE);

  const mutation = useMutation({
    mutationFn: () =>
      api<Schemas["EmployeeDetail"]>("/employees", {
        method: "POST",
        body: {
          name,
          registration_number: registration,
          cpf: cpf || null,
          hire_date: hireDate,
          schedule: scheduleToApi(schedule),
        },
      }),
    onSuccess: (employee) => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
      navigate(`/funcionarios/${employee.id}`);
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal title="Novo funcionário" onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-4">
        <ErrorMessage error={mutation.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="name">
              Nome
            </label>
            <input id="name" required className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="registration">
              Matrícula
            </label>
            <input
              id="registration"
              required
              className="input"
              value={registration}
              onChange={(e) => setRegistration(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="cpf">
              CPF (opcional)
            </label>
            <input id="cpf" className="input" value={cpf} onChange={(e) => setCpf(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="hire_date">
              Data de admissão
            </label>
            <input
              id="hire_date"
              type="date"
              required
              className="input"
              value={hireDate}
              onChange={(e) => setHireDate(e.target.value)}
            />
          </div>
        </div>
        <h3 className="border-t border-slate-200 pt-4 font-semibold text-slate-800">Horário fixo</h3>
        <ScheduleFields value={schedule} onChange={setSchedule} />
        <p className="rounded-md bg-slate-50 p-3 text-xs text-slate-500">
          O cadastro do rosto para o terminal de ponto será feito nesta tela a partir da Fase 5.
        </p>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Salvando…" : "Cadastrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
