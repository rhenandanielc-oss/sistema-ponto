"""Cifragem dos templates biométricos: AES-256-GCM, chave fora do banco (BIOMETRICS.md §5)."""

import base64
import os
from dataclasses import dataclass

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

EMBEDDING_DIM = 128


class BiometricKeyError(ValueError):
    pass


def parse_key(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise BiometricKeyError("BIOMETRIC_KEY deve estar em base64.") from exc
    if len(key) != 32:
        raise BiometricKeyError("BIOMETRIC_KEY deve ter 32 bytes (256 bits) em base64.")
    return key


@dataclass(frozen=True)
class SealedTemplate:
    ciphertext: bytes
    nonce: bytes
    key_id: str


class TemplateCipher:
    def __init__(self, key: bytes, key_id: str) -> None:
        self._aead = AESGCM(key)
        self.key_id = key_id

    def seal(self, embedding: np.ndarray, *, employee_id: int) -> SealedTemplate:
        nonce = os.urandom(12)
        data = np.asarray(embedding, dtype="<f4").reshape(-1).tobytes()
        # O id do funcionário entra como dado associado: um template copiado para outro funcionário
        # no banco deixa de ser decifrável.
        ciphertext = self._aead.encrypt(nonce, data, _aad(employee_id))
        return SealedTemplate(ciphertext=ciphertext, nonce=nonce, key_id=self.key_id)

    def open(self, sealed: SealedTemplate, *, employee_id: int) -> np.ndarray:
        if sealed.key_id != self.key_id:
            raise BiometricKeyError(f"Template cifrado com outra chave ({sealed.key_id}).")
        data = self._aead.decrypt(sealed.nonce, sealed.ciphertext, _aad(employee_id))
        return np.frombuffer(data, dtype="<f4").copy()


def _aad(employee_id: int) -> bytes:
    return f"employee:{employee_id}".encode()
