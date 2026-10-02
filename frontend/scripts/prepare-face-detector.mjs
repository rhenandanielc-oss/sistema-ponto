// Copia o runtime WASM do MediaPipe e baixa (com conferência de SHA-256) o modelo de detecção facial
// para public/mediapipe/. Assim o terminal não depende de nenhum servidor externo em produção.
// Modelo: BlazeFace short range (Apache 2.0). Usado só para enquadramento — a identificação é no servidor.
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const target = join(root, "public", "mediapipe");
const MODEL = {
  file: "blaze_face_short_range.tflite",
  url: "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
  sha256: "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
};

const sha256 = (data) => createHash("sha256").update(data).digest("hex");

mkdirSync(target, { recursive: true });
cpSync(join(root, "node_modules", "@mediapipe", "tasks-vision", "wasm"), join(target, "wasm"), { recursive: true });

const modelPath = join(target, MODEL.file);
if (!existsSync(modelPath) || sha256(readFileSync(modelPath)) !== MODEL.sha256) {
  const response = await fetch(MODEL.url);
  if (!response.ok) throw new Error(`Falha ao baixar ${MODEL.url}: ${response.status}`);
  const data = Buffer.from(await response.arrayBuffer());
  if (sha256(data) !== MODEL.sha256) throw new Error(`${MODEL.file}: SHA-256 inesperado`);
  writeFileSync(modelPath, data);
}
console.log(`Detector facial pronto em ${target}`);
