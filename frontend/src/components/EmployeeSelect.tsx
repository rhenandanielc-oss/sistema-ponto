import { useQuery } from "@tanstack/react-query";

import { api, type Schemas } from "../api/client";

export function useAllEmployees() {
  return useQuery({
    queryKey: ["employees", "all"],
    queryFn: () =>
      api<Schemas["Page_EmployeeOut_"]>("/employees", { query: { page_size: 200, sort: "name" } }),
    select: (page) => page.items,
  });
}

export function EmployeeSelect({
  value,
  onChange,
  allowAll = false,
  id = "employee",
}: {
  value: number | null;
  onChange: (id: number | null) => void;
  allowAll?: boolean;
  id?: string;
}) {
  const { data = [] } = useAllEmployees();
  return (
    <select
      id={id}
      className="input"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
    >
      <option value="">{allowAll ? "Todos os funcionários" : "Selecione…"}</option>
      {data.map((e) => (
        <option key={e.id} value={e.id}>
          {e.name} ({e.registration_number}){e.status === "INACTIVE" ? " — inativo" : ""}
        </option>
      ))}
    </select>
  );
}
