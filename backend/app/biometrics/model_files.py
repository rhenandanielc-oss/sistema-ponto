"""Modelos de visão usados no servidor (BIOMETRICS.md §3).

Licenças confirmadas em 2026-10-01 no repositório opencv/opencv_zoo:
* YuNet (detecção de rosto): MIT.
* SFace (reconhecimento): Apache 2.0.

Os arquivos não ficam no Git: são baixados por `python -m app.cli download-models` e conferidos
pelo SHA-256.
"""

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    sha256: str


DETECTOR = ModelFile(
    "face_detection_yunet_2023mar.onnx",
    f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)
RECOGNIZER = ModelFile(
    "face_recognition_sface_2021dec.onnx",
    f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
)
ALL = (DETECTOR, RECOGNIZER)

# Templates gerados por modelos diferentes não são comparáveis (DATABASE.md §5).
MODEL_VERSION = "sface-2021dec"


class ModelIntegrityError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_path(directory: Path, model: ModelFile) -> Path:
    path = directory / model.name
    if not path.is_file():
        raise ModelIntegrityError(
            f"Modelo {model.name} não encontrado em {directory}. "
            "Rode: python -m app.cli download-models"
        )
    if sha256_of(path) != model.sha256:
        raise ModelIntegrityError(f"Modelo {model.name} com SHA-256 diferente do esperado.")
    return path


def download(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for model in ALL:
        path = directory / model.name
        if not (path.is_file() and sha256_of(path) == model.sha256):
            tmp = path.with_suffix(".part")
            # URL fixa; o arquivo é conferido pelo SHA-256 logo abaixo.
            urllib.request.urlretrieve(model.url, tmp)
            if sha256_of(tmp) != model.sha256:
                tmp.unlink()
                raise ModelIntegrityError(f"Download de {model.name} com SHA-256 inesperado.")
            tmp.replace(path)
        paths.append(path)
    return paths
