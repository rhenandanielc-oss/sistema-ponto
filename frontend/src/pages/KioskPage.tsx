import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, type Schemas } from "../api/client";
import { CameraError, captureFrame, openCamera, stopCamera } from "../kiosk/camera";
import { analyzeFrame, framingMessage, loadFaceDetector } from "../kiosk/faceDetector";
import { getDeviceToken, kioskApi, setDeviceToken } from "../kiosk/api";
import { RECORD_TYPE_LABELS, formatDate, formatMinutes, formatTime } from "../lib/format";

type Identified = Schemas["IdentifyOut"];
type Bank = Schemas["KioskHourBankOut"];

type State =
  | { kind: "setup"; message?: string }
  | { kind: "scanning"; hint: string }
  | { kind: "identifying" }
  | { kind: "identified"; data: Identified }
  | { kind: "saving"; data: Identified }
  | { kind: "done"; message: string }
  | { kind: "bank"; data: Bank }
  | { kind: "error"; message: string; retryInMs: number };

const RECORD_TYPES = ["ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT"] as const;
const IDLE_MS = 15_000; // sem toque na tela de botões, volta ao início
const DONE_MS = 5_000;
const ERROR_RETRY_MS = 3_000;
const STABLE_FRAMES = 3; // quadros bons seguidos antes de enviar

/** Mensagem amigável para cada erro devolvido pela API (BIOMETRICS.md §9). */
function friendly(error: unknown): string {
  if (!(error instanceof ApiError)) return "Erro inesperado. Tente novamente.";
  switch (error.code) {
    case "NETWORK_ERROR":
      return "Sem conexão. Tentando novamente…";
    case "FACE_NOT_RECOGNIZED":
      return "Não reconhecido. Tente novamente ou procure o administrador.";
    case "DUPLICATE_RECORD":
      return "Registro já efetuado.";
    case "EMPLOYEE_INACTIVE":
      return "Cadastro inativo. Procure o administrador.";
    default:
      return error.message;
  }
}

export function KioskPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [state, setState] = useState<State>(() => (getDeviceToken() ? { kind: "scanning", hint: "Iniciando câmera…" } : { kind: "setup" }));
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [deviceName, setDeviceName] = useState<string | null>(null);
  const [clock, setClock] = useState(() => new Date());
  const busy = useRef(false);

  const reset = useCallback(() => setState({ kind: "scanning", hint: "Olhe para a câmera" }), []);

  const handleError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.code === "DEVICE_NOT_AUTHORIZED") {
      setDeviceToken(null);
      setState({ kind: "setup", message: "Este terminal não está mais autorizado. Informe uma nova chave." });
      return;
    }
    setState({ kind: "error", message: friendly(error), retryInMs: ERROR_RETRY_MS });
  }, []);

  // Relógio exibido (o horário oficial da batida é sempre o do servidor).
  useEffect(() => {
    const id = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  // Confere o terminal ao iniciar.
  const active = state.kind !== "setup";
  useEffect(() => {
    if (!active) return;
    kioskApi.ping().then((p) => setDeviceName(p.device), handleError);
  }, [active, handleError]);

  // Câmera ligada enquanto o terminal estiver configurado.
  useEffect(() => {
    if (!active || !videoRef.current) return;
    let cancelled = false;
    openCamera(videoRef.current)
      .then((stream) => {
        if (cancelled) stopCamera(stream);
        else {
          streamRef.current = stream;
          setCameraError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setCameraError(err instanceof CameraError ? err.message : "Câmera indisponível.");
      });
    return () => {
      cancelled = true;
      stopCamera(streamRef.current);
      streamRef.current = null;
    };
  }, [active]);

  const identify = useCallback(async () => {
    const video = videoRef.current;
    if (!video || busy.current) return;
    busy.current = true;
    setState({ kind: "identifying" });
    try {
      const frame = await captureFrame(video);
      const data = await kioskApi.identify(frame);
      setState({ kind: "identified", data });
    } catch (error) {
      handleError(error);
    } finally {
      busy.current = false;
    }
  }, [handleError]);

  // Varredura: quando o rosto está bem enquadrado por alguns quadros seguidos, envia automaticamente.
  const scanning = state.kind === "scanning";
  useEffect(() => {
    if (!scanning || cameraError) return;
    let stop = false;
    let stable = 0;
    let timer = 0;
    (async () => {
      const detector = await loadFaceDetector();
      const tick = () => {
        if (stop) return;
        const video = videoRef.current;
        if (detector && video && video.readyState >= 2) {
          const hint = framingMessage(analyzeFrame(detector, video));
          stable = hint ? 0 : stable + 1;
          setState((s) => (s.kind === "scanning" ? { kind: "scanning", hint: hint ?? "Não se mova…" } : s));
          if (stable >= STABLE_FRAMES) {
            void identify();
            return;
          }
        } else if (!detector) {
          setState((s) => (s.kind === "scanning" ? { kind: "scanning", hint: "Toque em Identificar" } : s));
        }
        timer = window.setTimeout(tick, 250);
      };
      tick();
    })();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [scanning, cameraError, identify]);

  // Telas temporárias voltam sozinhas ao início.
  useEffect(() => {
    const ms =
      state.kind === "identified"
        ? IDLE_MS
        : state.kind === "done"
          ? DONE_MS
          : state.kind === "error"
            ? state.retryInMs
            : state.kind === "bank"
              ? state.data.screen_seconds * 1000
              : 0;
    if (!ms) return;
    const id = window.setTimeout(reset, ms);
    return () => window.clearTimeout(id);
  }, [state, reset]);

  async function punch(data: Identified, type: (typeof RECORD_TYPES)[number]) {
    setState({ kind: "saving", data });
    try {
      const result = await kioskApi.record(data.identification_token, type);
      setState({
        kind: "done",
        message: `${RECORD_TYPE_LABELS[result.type]} registrada às ${formatTime(result.recorded_at)}`,
      });
    } catch (error) {
      handleError(error);
    }
  }

  async function showBank(data: Identified) {
    setState({ kind: "saving", data });
    try {
      setState({ kind: "bank", data: await kioskApi.hourBank(data.identification_token) });
    } catch (error) {
      handleError(error);
    }
  }

  if (state.kind === "setup") {
    return (
      <SetupScreen
        message={state.message}
        onReady={(name) => {
          setDeviceName(name);
          reset();
        }}
      />
    );
  }

  const showCamera = state.kind === "scanning" || state.kind === "identifying";
  return (
    <div className="flex min-h-screen flex-col bg-slate-900 text-white">
      <header className="flex items-center justify-between px-6 py-4 text-slate-300">
        <span className="font-semibold">Ponto{deviceName ? ` — ${deviceName}` : ""}</span>
        <span className="text-3xl font-bold tabular-nums text-white" aria-label="Hora atual">
          {clock.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
        </span>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-6 px-6 pb-8">
        <div className={`relative w-full max-w-xl overflow-hidden rounded-2xl bg-black ${showCamera ? "" : "hidden"}`}>
          <video ref={videoRef} muted playsInline className="aspect-video w-full -scale-x-100 object-cover" />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-3/4 w-2/5 rounded-[50%] border-4 border-white/60" />
          </div>
        </div>

        {cameraError && (
          <p role="alert" className="rounded-lg bg-red-600 px-6 py-4 text-xl">
            {cameraError}
          </p>
        )}

        {state.kind === "scanning" && !cameraError && (
          <>
            <p className="text-2xl" aria-live="polite">
              {state.hint}
            </p>
            <button type="button" className="rounded-xl bg-white/10 px-6 py-3 text-lg hover:bg-white/20" onClick={() => void identify()}>
              Identificar
            </button>
          </>
        )}

        {state.kind === "identifying" && <p className="text-2xl">Identificando…</p>}

        {(state.kind === "identified" || state.kind === "saving") && (
          <div className="w-full max-w-2xl text-center">
            <p className="text-lg text-slate-300">Olá,</p>
            <h1 className="mb-8 text-4xl font-bold">{state.data.employee_name}</h1>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {RECORD_TYPES.map((type) => {
                const allowed = state.data.allowed_types.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    disabled={!allowed || state.kind === "saving"}
                    onClick={() => void punch(state.data, type)}
                    className="rounded-2xl bg-indigo-600 px-6 py-8 text-2xl font-semibold hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-400"
                  >
                    {RECORD_TYPE_LABELS[type]}
                  </button>
                );
              })}
            </div>
            <div className="mt-6 flex flex-wrap justify-center gap-4">
              <button
                type="button"
                disabled={state.kind === "saving"}
                onClick={() => void showBank(state.data)}
                className="rounded-xl bg-white/10 px-6 py-4 text-lg hover:bg-white/20"
              >
                Ver meu banco de horas
              </button>
              <button type="button" onClick={reset} className="rounded-xl px-6 py-4 text-lg text-slate-300 hover:bg-white/10">
                Cancelar
              </button>
            </div>
          </div>
        )}

        {state.kind === "done" && (
          <p role="status" className="rounded-2xl bg-green-600 px-10 py-8 text-center text-3xl font-semibold">
            ✔ {state.message}
          </p>
        )}

        {state.kind === "error" && (
          <p role="alert" className="rounded-2xl bg-amber-600 px-10 py-8 text-center text-2xl font-semibold">
            {state.message}
          </p>
        )}

        {state.kind === "bank" && <BankScreen data={state.data} onClose={reset} />}
      </main>
    </div>
  );
}

function BankScreen({ data, onClose }: { data: Bank; onClose: () => void }) {
  const signed = (m: number) => formatMinutes(m, true);
  return (
    <div className="w-full max-w-2xl rounded-2xl bg-white p-6 text-slate-900">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{data.employee_name}</h1>
        <button type="button" onClick={onClose} className="rounded-lg bg-slate-200 px-4 py-2 text-lg">
          Sair
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
        <Stat label="Saldo do banco" value={signed(data.balance_minutes)} />
        <Stat label="Extras no mês" value={formatMinutes(data.month_overtime_minutes)} />
        <Stat label="Faltantes no mês" value={formatMinutes(data.month_missing_minutes)} />
        <Stat label="Faltas no mês" value={String(data.month_absences)} />
      </div>
      <p className="mt-3 text-sm text-slate-600">
        Ciclo de pagamento {formatDate(data.pay_period_start)} a {formatDate(data.pay_period_end)}: extras{" "}
        {formatMinutes(data.pay_period_overtime_minutes)}, faltantes {formatMinutes(data.pay_period_missing_minutes)}.
      </p>
      <ul className="mt-4 max-h-64 divide-y divide-slate-100 overflow-y-auto text-sm">
        {[...data.days].reverse().map((d) => (
          <li key={d.date} className="flex justify-between py-1.5">
            <span>{formatDate(d.date)}</span>
            <span className="tabular-nums">
              {d.worked_minutes ? formatMinutes(d.worked_minutes) : "—"}{" "}
              {d.counts_for_bank && <span className={d.balance_minutes < 0 ? "text-red-700" : "text-green-700"}>({signed(d.balance_minutes)})</span>}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">Esta tela fecha sozinha em {data.screen_seconds} segundos.</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-100 p-3">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

function SetupScreen({ message, onReady }: { message?: string; onReady: (deviceName: string) => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(message ?? null);
  const [checking, setChecking] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setChecking(true);
    setError(null);
    try {
      const ping = await kioskApi.ping(token.trim());
      setDeviceToken(token.trim());
      onReady(ping.device);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "DEVICE_NOT_AUTHORIZED" ? "Chave inválida ou terminal desativado." : friendly(err));
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-6">
      <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6">
        <h1 className="text-2xl font-bold">Configurar terminal de ponto</h1>
        <p className="text-sm text-slate-600">
          Cole a chave gerada em Administração → Terminais. Ela fica guardada só neste navegador.
        </p>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
            {error}
          </p>
        )}
        <label className="label" htmlFor="device-token">
          Chave do terminal
        </label>
        <input id="device-token" required className="input font-mono" value={token} onChange={(e) => setToken(e.target.value)} />
        <button type="submit" className="btn-primary w-full" disabled={checking}>
          {checking ? "Verificando…" : "Ativar terminal"}
        </button>
      </form>
    </div>
  );
}
