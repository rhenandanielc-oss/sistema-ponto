/**
 * Detector de rosto no navegador (MediaPipe BlazeFace), só para enquadramento e para decidir quando
 * enviar um quadro. Não identifica ninguém: a identificação é feita no servidor (BIOMETRICS.md §3).
 * Se não carregar, o terminal continua funcionando com o botão "Identificar".
 */
import type { FaceDetector } from "@mediapipe/tasks-vision";

export interface Framing {
  faces: number;
  /** Largura do maior rosto em relação à largura do vídeo (0..1). */
  size: number;
  centered: boolean;
}

let loading: Promise<FaceDetector | null> | null = null;

export function loadFaceDetector(): Promise<FaceDetector | null> {
  loading ??= (async () => {
    try {
      const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const vision = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      return await FaceDetector.createFromOptions(vision, {
        baseOptions: { modelAssetPath: "/mediapipe/blaze_face_short_range.tflite", delegate: "CPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.6,
      });
    } catch {
      return null;
    }
  })();
  return loading;
}

export function analyzeFrame(detector: FaceDetector, video: HTMLVideoElement): Framing {
  const { detections } = detector.detectForVideo(video, performance.now());
  const width = video.videoWidth || 1;
  const height = video.videoHeight || 1;
  let size = 0;
  let centered = false;
  for (const d of detections) {
    const box = d.boundingBox;
    if (!box) continue;
    const ratio = box.width / width;
    if (ratio > size) {
      size = ratio;
      const cx = (box.originX + box.width / 2) / width;
      const cy = (box.originY + box.height / 2) / height;
      centered = Math.abs(cx - 0.5) < 0.2 && Math.abs(cy - 0.5) < 0.25;
    }
  }
  return { faces: detections.length, size, centered };
}

/** Rosto bom para enviar: um só, perto o suficiente e centralizado. */
export function framingMessage(f: Framing): string | null {
  if (f.faces === 0) return "Posicione o rosto na moldura";
  if (f.faces > 1) return "Apenas uma pessoa por vez";
  if (f.size < 0.18) return "Aproxime-se da câmera";
  if (!f.centered) return "Centralize o rosto na moldura";
  return null;
}
