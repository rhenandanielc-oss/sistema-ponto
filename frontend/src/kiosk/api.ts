/** Comunicação do terminal com a API: autenticado pelo token do dispositivo, nunca por usuário. */
import { ApiError, type Schemas } from "../api/client";

const STORAGE_KEY = "ponto-kiosk-device-token";
const BASE = "/api/v1/kiosk";

export function getDeviceToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setDeviceToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* navegador sem armazenamento: o token terá de ser informado de novo */
  }
}

async function call<T>(path: string, init: RequestInit, token = getDeviceToken()): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ...(init.headers ?? {}), Authorization: `Device ${token ?? ""}` },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Sem conexão com o servidor.");
  }
  if (!response.ok) {
    let code = "ERROR";
    let message = "Erro inesperado.";
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } };
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      /* resposta sem corpo */
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export const kioskApi = {
  ping: (token?: string) => call<Schemas["PingOut"]>("/ping", { method: "GET" }, token),
  identify: (image: Blob) => {
    const form = new FormData();
    form.append("image", image, "rosto.jpg");
    return call<Schemas["IdentifyOut"]>("/identify", { method: "POST", body: form });
  },
  record: (identificationToken: string, type: string) =>
    call<Schemas["KioskRecordOut"]>("/records", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identification_token: identificationToken, type }),
    }),
  hourBank: (identificationToken: string) =>
    call<Schemas["KioskHourBankOut"]>("/hour-bank", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identification_token: identificationToken }),
    }),
};
