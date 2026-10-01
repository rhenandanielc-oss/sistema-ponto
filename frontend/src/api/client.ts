import type { components } from "./schema";

export type Schemas = components["schemas"];

const BASE = "/api/v1";

/** Erro no formato padrão da API: {"error": {"code", "message", "details", "request_id"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Mensagens dos campos inválidos (erros 422), para exibir no formulário. */
  fieldMessages(): string[] {
    const fields = this.details.fields;
    if (!Array.isArray(fields)) return [];
    return fields.map((f: { loc?: string[]; message?: string }) => {
      const field = (f.loc ?? []).filter((p) => p !== "body").join(".");
      const message = (f.message ?? "").replace(/^Value error, /, "");
      return field ? `${field}: ${message}` : message;
    });
  }
}

// O token de acesso fica só em memória (nunca em localStorage — SECURITY.md §3).
let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;
let refreshing: Promise<boolean> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown> };
    };
    const error = body.error ?? {};
    return new ApiError(
      response.status,
      error.code ?? "ERROR",
      error.message ?? "Erro inesperado.",
      error.details ?? {},
    );
  } catch {
    return new ApiError(response.status, "ERROR", "Erro de comunicação com o servidor.");
  }
}

/** Renova o token de acesso usando o cookie de refresh. Chamadas simultâneas compartilham a renovação. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
      if (!response.ok) return false;
      const body = (await response.json()) as Schemas["TokenResponse"];
      accessToken = body.access_token;
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  query?: Query;
  body?: unknown;
}

export async function api<T>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Sem conexão com o servidor.");
  }

  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, options, false);
    accessToken = null;
    onSessionLost?.();
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
