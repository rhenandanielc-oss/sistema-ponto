import { NavLink, Outlet } from "react-router";

import { useAuth } from "../lib/auth";

const LINKS = [
  { to: "/funcionarios", label: "Funcionários" },
  { to: "/historico", label: "Histórico" },
  { to: "/banco-de-horas", label: "Banco de horas" },
  { to: "/admin", label: "Administração" },
];

export function Layout() {
  const { admin, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-bold text-indigo-700">Ponto</span>
          <nav className="flex flex-wrap gap-1" aria-label="Menu principal">
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm font-medium ${
                    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
            <span className="hidden sm:inline">{admin?.name}</span>
            <button type="button" className="btn-secondary" onClick={() => void logout()}>
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
