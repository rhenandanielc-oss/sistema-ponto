import { Navigate, Route, Routes, useLocation } from "react-router";
import type { ReactNode } from "react";

import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { useAuth } from "./lib/auth";
import { AdminPage } from "./pages/AdminPage";
import { EmployeeDetailPage } from "./pages/EmployeeDetailPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HourBankEmployeePage } from "./pages/HourBankEmployeePage";
import { HourBankPage } from "./pages/HourBankPage";
import { KioskPage } from "./pages/KioskPage";
import { LoginPage } from "./pages/LoginPage";
import { PayrollPage } from "./pages/PayrollPage";

/** Rotas administrativas: sem sessão, vai para /login e volta depois. */
function RequireAdmin({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Loading />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/kiosk" element={<KioskPage />} />
      <Route
        element={
          <RequireAdmin>
            <Layout />
          </RequireAdmin>
        }
      >
        <Route path="/funcionarios" element={<EmployeesPage />} />
        <Route path="/funcionarios/:id" element={<EmployeeDetailPage />} />
        {/* A carga horária fica no cadastro do funcionário (decisão do responsável). */}
        <Route path="/jornadas" element={<Navigate to="/funcionarios" replace />} />
        <Route path="/historico" element={<HistoryPage />} />
        <Route path="/banco-de-horas" element={<HourBankPage />} />
        <Route path="/banco-de-horas/:id" element={<HourBankEmployeePage />} />
        <Route path="/pagamento" element={<PayrollPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/funcionarios" replace />} />
    </Routes>
  );
}
