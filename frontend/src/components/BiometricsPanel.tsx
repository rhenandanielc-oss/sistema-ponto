import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Schemas } from "../api/client";
import { CameraError, captureFrame, openCamera, stopCamera } from "../kiosk/camera";
import { formatDateTime } from "../lib/format";
import { Badge, ErrorMessage, Modal } from "./ui";

type Status = Schemas["BiometricStatusOut"];

function uploadPhoto(employeeId: number, photo: Blob): Promise<Status> {
  const form = new FormData();
  form.append("image", photo, "rosto.jpg");
  return api<Status>(`/employees/${employeeId}/biometric-templates`, { method: "POST", body: form });
}

export function BiometricsPanel({ employeeId, active }: { employeeId: number; active: boolean }) {
  const queryClient = useQueryClient();
  const [capturing, setCapturing] = useState(false);
  const key = ["employee", employeeId, "biometrics"];
  const status = useQuery({ queryKey: key, queryFn: () => api<Status>(`/employees/${employeeId}/biometric-status`) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const consent = useMutation({
    mutationFn: () => api<Status>(`/employees/${employeeId}/biometric-consent`, { method: "POST", body: {} }),
    onSuccess: refresh,
  });
  const revoke = useMutation({
    mutationFn: () => api(`/employees/${employeeId}/biometric-consent`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => api(`/employees/${employeeId}/biometric-templates`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const s = status.data;
  return (
    <section className="card mt-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-800">Rosto para o terminal de ponto</h2>
        {s && (s.ready ? <Badge tone="green">Pronto para bater ponto</Badge> : <Badge tone="amber">Não cadastrado</Badge>)}
      </div>
      <ErrorMessage error={status.error ?? consent.error ?? revoke.error ?? remove.error} />
      {s && !s.consent && (
        <div className="space-y-3 text-sm">
          <p className="text-slate-600">
            A biometria facial é um dado sensível (LGPD). Antes de cadastrar o rosto, confirme que o funcionário leu e
            aceitou o termo de uso. Só é guardado um código numérico cifrado do rosto — nunca a foto.
          </p>
          <button
            type="button"
            className="btn-primary"
            disabled={!active || consent.isPending}
            onClick={() => window.confirm("Confirmar que o funcionário consentiu com o uso da biometria facial?") && consent.mutate()}
          >
            Registrar consentimento
          </button>
          {!active && <p className="text-slate-500">Funcionário inativo.</p>}
        </div>
      )}
      {s && s.consent && (
        <div className="space-y-3 text-sm">
          <p className="text-slate-600">
            Consentimento registrado em {s.consent_granted_at ? formatDateTime(s.consent_granted_at) : "—"} (termo{" "}
            {s.term_version}). Fotos cadastradas: <strong>{s.templates}</strong> de {s.max_templates}.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary"
              disabled={!active || s.templates >= s.max_templates}
              onClick={() => setCapturing(true)}
            >
              {s.templates ? "Adicionar foto" : "Cadastrar rosto"}
            </button>
            {s.templates > 0 && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => window.confirm("Excluir as fotos cadastradas? O funcionário não poderá bater ponto até cadastrar de novo.") && remove.mutate()}
              >
                Excluir fotos
              </button>
            )}
            <button
              type="button"
              className="btn-secondary text-red-700"
              onClick={() => window.confirm("Revogar o consentimento? As fotos cadastradas serão excluídas.") && revoke.mutate()}
            >
              Revogar consentimento
            </button>
          </div>
        </div>
      )}
      {capturing && s && (
        <CaptureModal
          employeeId={employeeId}
          initial={s.templates}
          max={s.max_templates}
          onDone={() => {
            setCapturing(false);
            refresh();
          }}
        />
      )}
    </section>
  );
}

function CaptureModal({
  employeeId,
  initial,
  max,
  onDone,
}: {
  employeeId: number;
  initial: number;
  max: number;
  onDone: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [count, setCount] = useState(initial);
  const upload = useMutation({
    mutationFn: async () => uploadPhoto(employeeId, await captureFrame(videoRef.current!, 960)),
    onSuccess: (status) => setCount(status.templates),
  });

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    if (videoRef.current) {
      openCamera(videoRef.current)
        .then((s) => (cancelled ? stopCamera(s) : (stream = s)))
        .catch((err: unknown) => {
          if (!cancelled) setCameraError(err instanceof CameraError ? err.message : "Câmera indisponível.");
        });
    }
    return () => {
      cancelled = true;
      stopCamera(stream);
    };
  }, []);

  return (
    <Modal title="Cadastrar rosto" onClose={onDone}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Peça ao funcionário para olhar para a câmera, sem óculos escuros nem boné, em local bem iluminado. Tire 3
          fotos com pequenas variações (de frente e levemente para os lados). As fotos não são guardadas.
        </p>
        {cameraError && <ErrorMessage error={new Error(cameraError)} />}
        <video ref={videoRef} muted playsInline className="aspect-video w-full -scale-x-100 rounded-lg bg-black object-cover" />
        <ErrorMessage error={upload.error} />
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-600" aria-live="polite">
            Fotos cadastradas: {count} de {max}
          </span>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onDone}>
              Concluir
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={upload.isPending || !!cameraError || count >= max}
              onClick={() => upload.mutate()}
            >
              {upload.isPending ? "Enviando…" : "Tirar foto"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
