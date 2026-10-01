"""Matching, cifragem e integridade dos modelos (BIOMETRICS.md)."""

import base64
from pathlib import Path

import numpy as np
import pytest
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError

from app.biometrics import model_files
from app.biometrics.crypto import BiometricKeyError, TemplateCipher, parse_key
from app.biometrics.engine import FaceError, FakeFaceEngine
from app.biometrics.matcher import best_match, normalize
from app.core.config import DEV_BIOMETRIC_KEY, Settings

RNG = np.random.default_rng(42)


def vec() -> np.ndarray:
    return normalize(RNG.standard_normal(128).astype(np.float32))


def near(v: np.ndarray, noise: float) -> np.ndarray:
    """Vetor próximo de `v`: ruído relativo `noise` (0,2 ≈ mesma pessoa em outra foto)."""
    return normalize(v + noise * RNG.standard_normal(128).astype(np.float32) / np.sqrt(128))


def test_match_accepts_same_person_and_rejects_strangers() -> None:
    ana, bruno = vec(), vec()
    candidates = [(1, ana), (1, near(ana, 0.1)), (2, bruno)]
    result = best_match(near(ana, 0.2), candidates, threshold=0.363, margin=0.05)
    assert result.employee_id == 1
    assert result.score > 0.8
    stranger = best_match(vec(), candidates, threshold=0.363, margin=0.05)
    assert stranger.employee_id is None


def test_margin_rejects_ambiguous_match() -> None:
    """Dois funcionários parecidos demais: melhor não identificar do que identificar errado."""
    ana = vec()
    twin = near(ana, 0.05)
    result = best_match(near(ana, 0.05), [(1, ana), (2, twin)], threshold=0.363, margin=0.05)
    assert result.score >= 0.363
    assert result.employee_id is None


def test_no_candidates() -> None:
    assert best_match(vec(), [], threshold=0.3, margin=0.0).employee_id is None


def test_cipher_roundtrip_and_binding_to_employee() -> None:
    cipher = TemplateCipher(parse_key(DEV_BIOMETRIC_KEY), "k1")
    v = vec()
    sealed = cipher.seal(v, employee_id=7)
    assert v.tobytes() not in sealed.ciphertext  # o vetor não aparece em claro
    assert np.allclose(cipher.open(sealed, employee_id=7), v)
    with pytest.raises(InvalidTag):
        cipher.open(sealed, employee_id=8)  # template movido para outro funcionário
    other_key = TemplateCipher(bytes(range(32)), "k1")
    with pytest.raises(InvalidTag):
        other_key.open(sealed, employee_id=7)
    with pytest.raises(BiometricKeyError):
        TemplateCipher(parse_key(DEV_BIOMETRIC_KEY), "k2").open(sealed, employee_id=7)


def test_key_validation() -> None:
    with pytest.raises(BiometricKeyError):
        parse_key("não é base64!")
    with pytest.raises(BiometricKeyError):
        parse_key(base64.b64encode(b"curta").decode())


def test_production_rejects_fake_engine_and_dev_key() -> None:
    strong = {
        "environment": "production",
        "jwt_secret": "x" * 48,
        "cookie_secure": True,
    }
    real_key = base64.b64encode(bytes(range(32))).decode()
    with pytest.raises(ValidationError, match="BIOMETRIC_KEY"):
        Settings(**strong, face_engine="opencv")  # chave de desenvolvimento
    with pytest.raises(ValidationError, match="FACE_ENGINE"):
        Settings(**strong, biometric_key=real_key, face_engine="fake")
    Settings(**strong, biometric_key=real_key, face_engine="opencv")


def test_model_integrity(tmp_path: Path) -> None:
    with pytest.raises(model_files.ModelIntegrityError, match="não encontrado"):
        model_files.verified_path(tmp_path, model_files.DETECTOR)
    (tmp_path / model_files.DETECTOR.name).write_bytes(b"modelo adulterado")
    with pytest.raises(model_files.ModelIntegrityError, match="SHA-256"):
        model_files.verified_path(tmp_path, model_files.DETECTOR)


def test_fake_engine_contract() -> None:
    engine = FakeFaceEngine()
    a1 = engine.extract(b"FACE:ana#1").embedding
    a2 = engine.extract(b"FACE:ana#2").embedding
    assert np.allclose(a1, a2)
    for content, code in [
        (b"NOFACE", "FACE_NOT_FOUND"),
        (b"MULTI", "MULTIPLE_FACES"),
        (b"BLUR", "LOW_QUALITY"),
        (b"lixo", "INVALID_IMAGE"),
    ]:
        with pytest.raises(FaceError) as exc:
            engine.extract(content)
        assert exc.value.code == code
