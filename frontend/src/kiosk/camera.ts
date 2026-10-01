/** Câmera e captura de um único quadro. Nada é gravado: o quadro vai só para a requisição. */

export class CameraError extends Error {}

export async function openCamera(video: HTMLVideoElement): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new CameraError("Câmera indisponível neste navegador (é necessário HTTPS).");
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
  } catch (err) {
    const name = err instanceof DOMException ? err.name : "";
    throw new CameraError(
      name === "NotAllowedError"
        ? "Permissão da câmera negada. Libere a câmera nas configurações do navegador."
        : "Câmera indisponível. Verifique se ela está conectada.",
    );
  }
  video.srcObject = stream;
  try {
    await video.play();
  } catch (err) {
    // "AbortError": outra abertura da câmera substituiu esta (ex.: componente remontado). Não é falha.
    if (!(err instanceof DOMException && err.name === "AbortError")) throw err;
  }
  return stream;
}

export function stopCamera(stream: MediaStream | null): void {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Captura o quadro atual em JPEG, com no máximo 640 px de largura (bem abaixo do limite de 1 MB). */
export function captureFrame(video: HTMLVideoElement, maxWidth = 640): Promise<Blob> {
  const scale = Math.min(1, maxWidth / (video.videoWidth || maxWidth));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round((video.videoWidth || maxWidth) * scale);
  canvas.height = Math.round((video.videoHeight || maxWidth * 0.75) * scale);
  canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Falha ao capturar"))), "image/jpeg", 0.85),
  );
}
