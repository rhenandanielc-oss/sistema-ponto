"""Teste de fumaça do motor real (YuNet + SFace).

Roda só quando os modelos estão disponíveis: REAL_FACE_MODELS_DIR=<pasta>
(`python -m app.cli download-models --dir <pasta>`). Para o teste com rosto, informe também
REAL_FACE_SAMPLE=<foto com um rosto> — nenhuma foto real é versionada no repositório.
"""

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.biometrics.engine import FaceError, OpenCVFaceEngine

MODELS = os.environ.get("REAL_FACE_MODELS_DIR")
SAMPLE = os.environ.get("REAL_FACE_SAMPLE")
pytestmark = pytest.mark.skipif(not MODELS, reason="defina REAL_FACE_MODELS_DIR")


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_no_face_and_invalid_image() -> None:
    engine = OpenCVFaceEngine(Path(MODELS or ""), min_face_px=80)
    with pytest.raises(FaceError) as exc:
        engine.extract(jpeg(np.full((480, 640, 3), 127, np.uint8)))
    assert exc.value.code == "FACE_NOT_FOUND"
    with pytest.raises(FaceError) as exc:
        engine.extract(b"isto nao e uma imagem")
    assert exc.value.code == "INVALID_IMAGE"


@pytest.mark.skipif(not SAMPLE, reason="defina REAL_FACE_SAMPLE")
def test_same_face_matches_itself_after_changes() -> None:
    img = cv2.imread(SAMPLE or "")
    engine = OpenCVFaceEngine(Path(MODELS or ""), min_face_px=20)
    first = engine.extract(jpeg(img)).embedding
    altered = cv2.convertScaleAbs(cv2.resize(img, None, fx=0.8, fy=0.8), alpha=1.1, beta=10)
    second = engine.extract(jpeg(altered)).embedding
    assert float(np.dot(first, second)) > 0.363
    # Com o tamanho mínimo padrão do terminal, um rosto pequeno/distante é recusado.
    strict = OpenCVFaceEngine(Path(MODELS or ""), min_face_px=200)
    with pytest.raises(FaceError) as exc:
        strict.extract(jpeg(img))
    assert exc.value.code == "LOW_QUALITY"
