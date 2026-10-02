import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, refreshSession, setAccessToken, setSessionLostHandler, type Schemas } from "../api/client";

type Admin = Schemas["AdminOut"];

interface AuthState {
  status: "loading" | "authenticated" | "anonymous";
  admin: Admin | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [admin, setAdmin] = useState<Admin | null>(null);

  const clear = useCallback(() => {
    setAccessToken(null);
    setAdmin(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  // Ao abrir a página, tenta recuperar a sessão pelo cookie de refresh.
  useEffect(() => {
    setSessionLostHandler(clear);
    let cancelled = false;
    (async () => {
      if (await refreshSession()) {
        try {
          const me = await api<Admin>("/auth/me");
          if (!cancelled) {
            setAdmin(me);
            setStatus("authenticated");
          }
          return;
        } catch {
          /* cai para anônimo */
        }
      }
      if (!cancelled) setStatus("anonymous");
    })();
    return () => {
      cancelled = true;
      setSessionLostHandler(null);
    };
  }, [clear]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api<Schemas["TokenResponse"]>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    setAccessToken(result.access_token);
    setAdmin(result.admin);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      clear();
    }
  }, [clear]);

  const value = useMemo(() => ({ status, admin, login, logout }), [status, admin, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
