import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, setAccessToken, setSessionLostHandler } from "./client";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  setAccessToken(null);
  setSessionLostHandler(null);
});

describe("cliente da API", () => {
  it("envia o token e converte erros do formato padrão", async () => {
    setAccessToken("abc");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json(409, { error: { code: "DUPLICATE_RECORD", message: "Batida já registrada.", details: {} } }),
    );
    const error = await api("/time-records").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("DUPLICATE_RECORD");
    expect((error as ApiError).message).toBe("Batida já registrada.");
    const [, init] = fetchMock.mock.calls[0]!;
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer abc");
  });

  it("renova a sessão uma vez quando o token expira e repete a requisição", async () => {
    setAccessToken("velho");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json(401, { error: { code: "TOKEN_EXPIRED", message: "Sessão expirada." } }))
      .mockResolvedValueOnce(json(200, { access_token: "novo", expires_in: 900, admin: {} }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    await expect(api("/employees")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[1]![0]).toBe("/api/v1/auth/refresh");
    const retried = fetchMock.mock.calls[2]![1]?.headers as Record<string, string>;
    expect(retried.Authorization).toBe("Bearer novo");
  });

  it("avisa que a sessão acabou quando a renovação falha", async () => {
    const lost = vi.fn();
    setSessionLostHandler(lost);
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json(401, { error: { code: "UNAUTHENTICATED", message: "x" } }))
      .mockResolvedValueOnce(json(401, { error: { code: "UNAUTHENTICATED", message: "x" } }));
    await expect(api("/employees")).rejects.toBeInstanceOf(ApiError);
    expect(lost).toHaveBeenCalledOnce();
  });

  it("monta a query string ignorando filtros vazios", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json(200, {}));
    await api("/time-records", { query: { employee_id: null, type: "", page: 2, include_voided: false } });
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/v1/time-records?page=2&include_voided=false");
  });
});
