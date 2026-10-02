"""Detecção, checagem de qualidade e extração de embedding facial (BIOMETRICS.md §3).

A imagem só existe em memória durante a chamada: nada é gravado em disco.
"""

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Protocol

import cv2
import numpy as np

from app.biometrics import model_files
from app.biometrics.matcher import normalize
from app.core.config import get_settings

MAX_SIDE = 1280  # imagens maiores são reduzidas antes da detecção
DETECTION_SCORE = 0.8
MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 220.0
MIN_SHARPNESS = 25.0  # variância do Laplaciano no recorte do rosto


class FaceError(Exception):
    """Erro de imagem/rosto com código da API (API.md)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def no_face() -> FaceError:
    return FaceError("FACE_NOT_FOUND", "Nenhum rosto encontrado. Posicione o rosto na moldura.")


def multiple_faces() -> FaceError:
    return FaceError("MULTIPLE_FACES", "Mais de um rosto na imagem. Apenas uma pessoa por vez.")


def low_quality(message: str) -> FaceError:
    return FaceError("LOW_QUALITY", message)


def invalid_image() -> FaceError:
    return FaceError("INVALID_IMAGE", "Imagem inválida. Envie uma foto JPEG ou PNG.")


@dataclass(frozen=True)
class Extraction:
    embedding: np.ndarray  # vetor normalizado (128 dimensões)
    quality: float  # 0..1, informativo


class FaceEngine(Protocol):
    model_version: str

    def extract(self, image: bytes) -> Extraction:
        """Exige exatamente um rosto de boa qualidade; devolve o embedding ou levanta FaceError."""
        ...


def _decode(image: bytes) -> np.ndarray:
    if not image:
        raise invalid_image()
    try:
        decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:  # ex.: dimensões acima de MAX_IMAGE_PIXELS
        raise invalid_image() from None
    if decoded is None:
        raise invalid_image()
    h, w = decoded.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        decoded = cv2.resize(
            decoded, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
    return decoded


class OpenCVFaceEngine:
    """YuNet (detecção) + SFace (embedding), executados localmente em CPU."""

    model_version = model_files.MODEL_VERSION

    def __init__(self, models_dir: Path, min_face_px: int) -> None:
        detector = model_files.verified_path(models_dir, model_files.DETECTOR)
        recognizer = model_files.verified_path(models_dir, model_files.RECOGNIZER)
        self._detector = cv2.FaceDetectorYN.create(
            str(detector), "", (320, 320), DETECTION_SCORE, 0.3, 50
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer), "")
        self._min_face_px = min_face_px
        self._lock = Lock()  # os objetos do OpenCV não são seguros para threads

    def extract(self, image: bytes) -> Extraction:
        img = _decode(image)
        h, w = img.shape[:2]
        with self._lock:
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(img)
            if faces is None or len(faces) == 0:
                raise no_face()
            # Rostos muito pequenos ao fundo (alguém passando longe) não contam como segunda pessoa.
            relevant = [f for f in faces if min(f[2], f[3]) >= self._min_face_px / 2]
            if len(relevant) > 1:
                raise multiple_faces()
            face = max(faces, key=lambda f: f[2] * f[3])
            if min(face[2], face[3]) < self._min_face_px:
                raise low_quality("Rosto muito distante. Aproxime-se da câmera.")
            crop = self._recognizer.alignCrop(img, face)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            brightness = float(gray.mean())
            if not MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS:
                raise low_quality("Iluminação inadequada. Procure um local mais iluminado.")
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if sharpness < MIN_SHARPNESS:
                raise low_quality(
                    "Imagem tremida ou desfocada. Fique parado olhando para a câmera."
                )
            feature = self._recognizer.feature(crop)
        quality = min(1.0, float(face[14]) * min(1.0, sharpness / 200))
        return Extraction(embedding=normalize(feature), quality=quality)


class FakeFaceEngine:
    """Motor determinístico para testes automatizados (proibido em produção — ver config).

    Conteúdo da imagem → resultado:
    * b"NOFACE..." → nenhum rosto; b"MULTI..." → vários; b"BLUR..." → baixa qualidade;
    * b"FACE:<pessoa>" → embedding fixo daquela pessoa;
    * qualquer imagem válida (ex.: câmera simulada do navegador) → a pessoa "camera".
    """

    model_version = "fake-1"

    def extract(self, image: bytes) -> Extraction:
        if image.startswith(b"NOFACE"):
            raise no_face()
        if image.startswith(b"MULTI"):
            raise multiple_faces()
        if image.startswith(b"BLUR"):
            raise low_quality("Imagem tremida ou desfocada. Fique parado olhando para a câmera.")
        if image.startswith(b"FACE:"):
            label = image[5:].split(b"#")[0]
        else:
            _decode(image)
            label = b"camera"
        seed = int.from_bytes(hashlib.sha256(label).digest()[:8], "big")
        vector = np.random.default_rng(seed).standard_normal(128).astype(np.float32)
        return Extraction(embedding=normalize(vector), quality=1.0)


_build_lock = Lock()


@lru_cache
def get_face_engine() -> FaceEngine:
    settings = get_settings()
    with _build_lock:
        if settings.face_engine == "fake":
            return FakeFaceEngine()
        return OpenCVFaceEngine(Path(settings.face_models_dir), settings.face_min_size_px)
