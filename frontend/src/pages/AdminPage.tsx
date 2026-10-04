import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type Schemas } from "../api/client";
import { Badge, Empty, ErrorMessage, Loading, PageHeader, Pagination } from "../components/ui";
import { formatDate, formatDateTime, formatMoney, parseMoney, shortTime } from "../lib/format";
import { useAuth } from "../lib/auth";

const TABS = [
  { id: "holidays", label: "Feriados" },
  { id: "devices", label: "Terminais" },
  { id: "consumption", label: "Consumo" },
  { id: "admins", label: "Administradores" },
  { id: "settings", label: "Configurações" },
  { id: "audit", label: "Auditoria" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function AdminPage() {
  const [tab, setTab] = useState<TabId>("holidays");
  return (
    <>
      <PageHeader title="Administração" />
      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "holidays" && <HolidaysTab />}
      {tab === "devices" && <DevicesTab />}
      {tab === "consumption" && <ConsumptionItemsTab />}
      {tab === "admins" && <AdminsTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "audit" && <AuditTab />}
    </>
  );
}

function HolidaysTab() {
  const queryClient = useQueryClient();
  const year = new Date().getFullYear();
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [recurring, setRecurring] = useState(false);
  const holidays = useQuery({
    queryKey: ["holidays", year],
    queryFn: () =>
      api<Schemas["HolidayOut"][]>("/holidays", { query: { date_from: `${year}-01-01`, date_to: `${year}-12-31` } }),
  });
  const create = useMutation({
    mutationFn: () => api("/holidays", { method: "POST", body: { date, name, recurring } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["holidays"] });
      void queryClient.invalidateQueries({ queryKey: ["hour-bank"] });
      setDate("");
      setName("");
      setRecurring(false);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/holidays/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["holidays"] });
      void queryClient.invalidateQueries({ queryKey: ["hour-bank"] });
    },
  });
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form
        className="card space-y-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <h2 className="font-semibold">Novo feriado</h2>
        <ErrorMessage error={create.error} />
        <div>
          <label className="label" htmlFor="holiday-date">
            Data
          </label>
          <input id="holiday-date" type="date" required className="input" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="holiday-name">
            Nome
          </label>
          <input id="holiday-name" required className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={recurring} onChange={(e) => setRecurring(e.target.checked)} />
          Repete todo ano
        </label>
        <button type="submit" className="btn-primary" disabled={create.isPending}>
          Adicionar
        </button>
      </form>
      <div className="card lg:col-span-2">
        <h2 className="mb-3 font-semibold">Feriados de {year}</h2>
        <ErrorMessage error={remove.error} />
        {holidays.isLoading ? (
          <Loading />
        ) : holidays.data && holidays.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 text-sm">
            {holidays.data.map((h) => (
              <li key={h.id} className="flex items-center justify-between py-2">
                <span>
                  {h.recurring ? formatDate(h.date).slice(0, 5) : formatDate(h.date)} — {h.name}{" "}
                  {h.recurring && <Badge tone="indigo">todo ano</Badge>}
                </span>
                <button
                  type="button"
                  className="text-red-700 hover:underline"
                  onClick={() => window.confirm(`Excluir o feriado "${h.name}"?`) && remove.mutate(h.id)}
                >
                  Excluir
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Nenhum feriado cadastrado.</Empty>
        )}
      </div>
    </div>
  );
}

function ConsumptionItemsTab() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const items = useQuery({
    queryKey: ["consumption-items", "all"],
    queryFn: () => api<Schemas["ConsumptionItemOut"][]>("/consumption-items"),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["consumption-items"] });
  const create = useMutation({
    mutationFn: (body: { name: string; price_cents: number }) =>
      api("/consumption-items", { method: "POST", body }),
    onSuccess: () => {
      refresh();
      setName("");
      setPrice("");
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api(`/consumption-items/${id}`, { method: "PATCH", body }),
    onSuccess: refresh,
  });

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form
        className="card space-y-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          const cents = parseMoney(price);
          if (cents === null || cents <= 0) {
            setFormError("Preço inválido. Exemplo: 6,00");
            return;
          }
          setFormError(null);
          create.mutate({ name, price_cents: cents });
        }}
      >
        <h2 className="font-semibold">Novo item</h2>
        <p className="text-xs text-slate-500">
          Itens que o funcionário pode pegar (ex.: refrigerante). O consumo é lançado na ficha do funcionário e
          aparece em Pagamento para descontar.
        </p>
        {formError && (
          <p role="alert" className="text-sm text-red-700">
            {formError}
          </p>
        )}
        <ErrorMessage error={create.error} />
        <div>
          <label className="label" htmlFor="item-name">
            Nome
          </label>
          <input id="item-name" required className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="item-price">
            Preço (R$)
          </label>
          <input
            id="item-price"
            required
            inputMode="decimal"
            placeholder="6,00"
            className="input"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={create.isPending}>
          Adicionar item
        </button>
      </form>
      <div className="card lg:col-span-2">
        <h2 className="mb-3 font-semibold">Itens</h2>
        <ErrorMessage error={update.error} />
        {items.isLoading ? (
          <Loading />
        ) : items.data && items.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 text-sm">
            {items.data.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className={i.is_active ? "" : "text-slate-400"}>
                  {i.name} — {formatMoney(i.price_cents)} {!i.is_active && <Badge tone="slate">desativado</Badge>}
                </span>
                <span className="flex gap-3">
                  <button
                    type="button"
                    className="text-indigo-700 hover:underline"
                    onClick={() => {
                      const typed = window.prompt(`Novo preço de "${i.name}" (R$):`, (i.price_cents / 100).toFixed(2).replace(".", ","));
                      const cents = typed === null ? null : parseMoney(typed);
                      if (cents) update.mutate({ id: i.id, body: { price_cents: cents } });
                    }}
                  >
                    Alterar preço
                  </button>
                  <button
                    type="button"
                    className={i.is_active ? "text-red-700 hover:underline" : "text-indigo-700 hover:underline"}
                    onClick={() => update.mutate({ id: i.id, body: { is_active: !i.is_active } })}
                  >
                    {i.is_active ? "Desativar" : "Ativar"}
                  </button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Nenhum item cadastrado.</Empty>
        )}
      </div>
    </div>
  );
}

function DevicesTab() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [token, setToken] = useState<{ name: string; token: string } | null>(null);
  const devices = useQuery({ queryKey: ["devices"], queryFn: () => api<Schemas["DeviceOut"][]>("/devices") });
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["devices"] });
  const create = useMutation({
    mutationFn: () => api<Schemas["DeviceWithToken"]>("/devices", { method: "POST", body: { name } }),
    onSuccess: (d) => {
      setToken({ name: d.name, token: d.token });
      setName("");
      invalidate();
    },
  });
  const action = useMutation({
    mutationFn: ({ id, op }: { id: number; op: "activate" | "deactivate" | "rotate-token" }) =>
      api<Schemas["DeviceWithToken"] | Schemas["DeviceOut"]>(`/devices/${id}/${op}`, { method: "POST" }),
    onSuccess: (d) => {
      if ("token" in d) setToken({ name: d.name, token: d.token });
      invalidate();
    },
  });
  return (
    <div className="space-y-6">
      {token && (
        <div role="status" className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm">
          <p className="font-semibold">Chave do terminal “{token.name}” — copie agora, ela não será exibida de novo:</p>
          <code className="mt-2 block break-all rounded bg-white p-2 font-mono">{token.token}</code>
          <button type="button" className="btn-secondary mt-2" onClick={() => setToken(null)}>
            Já copiei
          </button>
        </div>
      )}
      <form
        className="card flex flex-wrap items-end gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grow">
          <label className="label" htmlFor="device-name">
            Nome do terminal
          </label>
          <input
            id="device-name"
            required
            className="input"
            placeholder="Ex.: Recepção"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={create.isPending}>
          Cadastrar terminal
        </button>
        <div className="w-full">
          <ErrorMessage error={create.error ?? action.error} />
        </div>
      </form>
      <div className="card overflow-x-auto">
        {devices.data && devices.data.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Terminal</th>
                <th>Situação</th>
                <th>Último contato</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {devices.data.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.is_active ? <Badge tone="green">Ativo</Badge> : <Badge tone="slate">Inativo</Badge>}</td>
                  <td>{d.last_seen_at ? formatDateTime(d.last_seen_at) : "nunca"}</td>
                  <td className="space-x-3 text-right">
                    <button
                      type="button"
                      className="text-indigo-700 hover:underline"
                      onClick={() =>
                        window.confirm("Gerar nova chave? O terminal precisará ser configurado de novo.") &&
                        action.mutate({ id: d.id, op: "rotate-token" })
                      }
                    >
                      Nova chave
                    </button>
                    <button
                      type="button"
                      className={d.is_active ? "text-red-700 hover:underline" : "text-green-700 hover:underline"}
                      onClick={() => action.mutate({ id: d.id, op: d.is_active ? "deactivate" : "activate" })}
                    >
                      {d.is_active ? "Desativar" : "Ativar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Nenhum terminal cadastrado.</Empty>
        )}
      </div>
    </div>
  );
}

function AdminsTab() {
  const queryClient = useQueryClient();
  const { admin: me } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const admins = useQuery({
    queryKey: ["admins"],
    queryFn: () => api<Schemas["Page_AdminOut_"]>("/admins", { query: { page_size: 200 } }),
  });
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["admins"] });
  const create = useMutation({
    mutationFn: () => api("/admins", { method: "POST", body: form }),
    onSuccess: () => {
      setForm({ name: "", email: "", password: "" });
      invalidate();
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api(`/admins/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
    onSuccess: invalidate,
  });
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form
        className="card space-y-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <h2 className="font-semibold">Novo administrador</h2>
        <ErrorMessage error={create.error} />
        {(["name", "email", "password"] as const).map((key) => (
          <div key={key}>
            <label className="label" htmlFor={`admin-${key}`}>
              {{ name: "Nome", email: "E-mail", password: "Senha (mínimo 10 caracteres)" }[key]}
            </label>
            <input
              id={`admin-${key}`}
              type={key === "password" ? "password" : key === "email" ? "email" : "text"}
              autoComplete={key === "password" ? "new-password" : "off"}
              minLength={key === "password" ? 10 : undefined}
              required
              className="input"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </div>
        ))}
        <button type="submit" className="btn-primary" disabled={create.isPending}>
          Cadastrar
        </button>
      </form>
      <div className="card lg:col-span-2">
        <ErrorMessage error={toggle.error} />
        <ul className="divide-y divide-slate-100 text-sm">
          {admins.data?.items.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                {a.name} <span className="text-slate-500">({a.email})</span>{" "}
                {!a.is_active && <Badge tone="slate">Inativo</Badge>}
              </span>
              {a.id !== me?.id && (
                <button
                  type="button"
                  className={a.is_active ? "text-red-700 hover:underline" : "text-green-700 hover:underline"}
                  onClick={() => toggle.mutate({ id: a.id, active: !a.is_active })}
                >
                  {a.is_active ? "Desativar" : "Ativar"}
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

type Settings = Schemas["CompanySettings"];

const SETTING_FIELDS: { key: keyof Settings; label: string; help: string; type: "number" | "time" }[] = [
  { key: "tolerance_per_mark_minutes", label: "Tolerância por batida (min)", help: "CLT: até 5 min.", type: "number" },
  { key: "tolerance_daily_minutes", label: "Tolerância diária (min)", help: "CLT: até 10 min.", type: "number" },
  { key: "min_minutes_between_records", label: "Intervalo mínimo entre batidas (min)", help: "Evita batida duplicada.", type: "number" },
  { key: "max_shift_hours", label: "Turno máximo (h)", help: "Depois disso, turno sem saída fica incompleto.", type: "number" },
  { key: "early_entry_window_hours", label: "Entrada antecipada (h)", help: "Para turnos que começam após a meia-noite.", type: "number" },
  { key: "night_start", label: "Início do período noturno", help: "CLT: 22:00.", type: "time" },
  { key: "night_end", label: "Fim do período noturno", help: "CLT: 05:00.", type: "time" },
  { key: "kiosk_hour_bank_screen_seconds", label: "Tela do banco de horas no terminal (s)", help: "Fecha sozinha após esse tempo.", type: "number" },
];

function SettingsTab() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/settings") });
  const [draft, setDraft] = useState<Partial<Record<keyof Settings, string>>>({});
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, string | number> = {};
      for (const field of SETTING_FIELDS) {
        const value = draft[field.key];
        if (value !== undefined) body[field.key] = field.type === "number" ? Number(value) : value;
      }
      return api<Settings>("/settings", { method: "PATCH", body });
    },
    onSuccess: () => {
      setDraft({});
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["hour-bank"] });
    },
  });
  if (!settings.data) return <Loading />;
  const current = settings.data;
  return (
    <form
      className="card space-y-4"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <ErrorMessage error={save.error} />
      {save.isSuccess && <p className="text-sm text-green-700">Configurações salvas.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {SETTING_FIELDS.map((field) => {
          const original = String(current[field.key]);
          const value = draft[field.key] ?? (field.type === "time" ? shortTime(original) : original);
          return (
            <div key={field.key}>
              <label className="label" htmlFor={`setting-${field.key}`}>
                {field.label}
              </label>
              <input
                id={`setting-${field.key}`}
                type={field.type}
                min={field.type === "number" ? 0 : undefined}
                className="input"
                value={value}
                onChange={(e) => setDraft({ ...draft, [field.key]: e.target.value })}
              />
              <p className="mt-1 text-xs text-slate-500">{field.help}</p>
            </div>
          );
        })}
      </div>
      <button type="submit" className="btn-primary" disabled={save.isPending || Object.keys(draft).length === 0}>
        Salvar configurações
      </button>
    </form>
  );
}

const AUDIT_ACTIONS: Record<string, string> = {
  "": "Todas as ações",
  "auth.": "Acessos (login, falhas, bloqueios)",
  "employee.": "Funcionários",
  "record.": "Batidas e ajustes",
  "hour_bank.": "Banco de horas",
  "holiday.": "Feriados",
  "device.": "Terminais",
  "admin.": "Administradores",
  "settings.": "Configurações",
};

function AuditTab() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const logs = useQuery({
    queryKey: ["audit", action, page],
    queryFn: () =>
      api<Schemas["Page_AuditLogOut_"]>("/audit-logs", { query: { action, page, page_size: 50 } }),
  });
  return (
    <div className="card">
      <select
        className="input mb-4 max-w-sm"
        aria-label="Filtrar ações"
        value={action}
        onChange={(e) => {
          setAction(e.target.value);
          setPage(1);
        }}
      >
        {Object.entries(AUDIT_ACTIONS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <ErrorMessage error={logs.error} />
      {logs.data && (
        <>
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Ação</th>
                  <th>Quem</th>
                  <th>Detalhes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.data.items.map((l) => (
                  <tr key={l.id}>
                    <td>{formatDateTime(l.occurred_at)}</td>
                    <td className="font-mono text-xs">{l.action}</td>
                    <td>
                      {l.actor_type === "ADMIN"
                        ? `Administrador #${l.actor_admin_id}`
                        : l.actor_type === "DEVICE"
                          ? `Terminal${l.actor_device_id ? ` #${l.actor_device_id}` : ""}`
                          : l.actor_type === "ANONYMOUS"
                            ? "Não autenticado"
                            : "Sistema"}
                    </td>
                    <td className="max-w-md truncate text-xs text-slate-600" title={JSON.stringify(l.after ?? l.before)}>
                      {l.entity_type ? `${l.entity_type} #${l.entity_id ?? ""} ` : ""}
                      {l.after ? JSON.stringify(l.after) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={50} total={logs.data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
