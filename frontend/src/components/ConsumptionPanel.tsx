import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type Schemas } from "../api/client";
import { formatDate, formatMoney, parseMoney } from "../lib/format";
import { toIsoDate } from "../lib/period";
import { Badge, Empty, ErrorMessage } from "./ui";

type Item = Schemas["ConsumptionItemOut"];
type Listing = Schemas["ConsumptionList"];

const OTHER = "outro";

/** Consumo do funcionário no ciclo de pagamento atual (BUSINESS-RULES.md §12). */
export function ConsumptionPanel({ employeeId }: { employeeId: number }) {
  const queryClient = useQueryClient();
  const key = ["employee", employeeId, "consumption"];
  const [itemId, setItemId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [date, setDate] = useState(() => toIsoDate(new Date()));
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const items = useQuery({
    queryKey: ["consumption-items", "active"],
    queryFn: () => api<Item[]>("/consumption-items", { query: { include_inactive: false } }),
  });
  const listing = useQuery({
    queryKey: key,
    queryFn: () => api<Listing>(`/employees/${employeeId}/consumption`),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ["payroll"] });
  };

  const add = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(`/employees/${employeeId}/consumption`, { method: "POST", body }),
    onSuccess: () => {
      refresh();
      setQuantity(1);
      setDescription("");
      setPrice("");
    },
  });
  const cancel = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api(`/consumption/${id}/cancel`, { method: "POST", body: { reason } }),
    onSuccess: refresh,
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const base = { quantity, entry_date: date };
    if (itemId === OTHER) {
      const cents = parseMoney(price);
      if (cents === null || cents <= 0) {
        setFormError("Valor inválido. Exemplo: 6,50");
        return;
      }
      add.mutate({ ...base, description, unit_price_cents: cents });
    } else if (itemId) {
      add.mutate({ ...base, item_id: Number(itemId) });
    } else {
      setFormError("Escolha o item.");
    }
  }

  const data = listing.data;
  return (
    <section className="card mt-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-800">Consumo (descontado no pagamento)</h2>
        {data && (
          <p className="text-sm">
            Total do ciclo: <span className="font-semibold">{formatMoney(data.total_cents)}</span>
          </p>
        )}
      </div>
      <form className="mb-4 flex flex-wrap items-end gap-3" onSubmit={submit}>
        <div>
          <label className="label" htmlFor="consumption-item">
            Item
          </label>
          <select
            id="consumption-item"
            className="input"
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
          >
            <option value="">Escolha…</option>
            {items.data?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} — {formatMoney(i.price_cents)}
              </option>
            ))}
            <option value={OTHER}>Outro (digitar)</option>
          </select>
        </div>
        {itemId === OTHER && (
          <>
            <div>
              <label className="label" htmlFor="consumption-description">
                Descrição
              </label>
              <input
                id="consumption-description"
                required
                className="input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="w-28">
              <label className="label" htmlFor="consumption-price">
                Valor (R$)
              </label>
              <input
                id="consumption-price"
                required
                inputMode="decimal"
                placeholder="6,50"
                className="input"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
          </>
        )}
        <div className="w-20">
          <label className="label" htmlFor="consumption-quantity">
            Qtd.
          </label>
          <input
            id="consumption-quantity"
            type="number"
            min={1}
            max={1000}
            required
            className="input"
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label" htmlFor="consumption-date">
            Data
          </label>
          <input
            id="consumption-date"
            type="date"
            required
            className="input"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={add.isPending}>
          Lançar consumo
        </button>
      </form>
      {formError && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {formError}
        </p>
      )}
      <ErrorMessage error={add.error ?? cancel.error} />
      {items.data && items.data.length === 0 && (
        <p className="mb-3 text-xs text-slate-500">
          Dica: cadastre os itens com preço em Administração → Consumo para lançar com um clique.
        </p>
      )}
      {data && data.items.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Item</th>
                <th>Qtd.</th>
                <th>Valor</th>
                <th>Total</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((c) => (
                <tr key={c.id} className={c.canceled_at ? "text-slate-400 line-through" : ""}>
                  <td>{formatDate(c.entry_date)}</td>
                  <td>{c.description}</td>
                  <td>{c.quantity}</td>
                  <td>{formatMoney(c.unit_price_cents)}</td>
                  <td>{formatMoney(c.total_cents)}</td>
                  <td className="text-right no-underline">
                    {c.canceled_at ? (
                      <Badge tone="slate">cancelado</Badge>
                    ) : (
                      <button
                        type="button"
                        className="text-red-700 hover:underline"
                        onClick={() => {
                          const reason = window.prompt("Motivo do cancelamento:");
                          if (reason && reason.trim().length >= 3) cancel.mutate({ id: c.id, reason: reason.trim() });
                        }}
                      >
                        Cancelar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>Nenhum consumo neste ciclo de pagamento.</Empty>
      )}
    </section>
  );
}
