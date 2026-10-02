import hashlib
import secrets
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.clock import now_utc
from app.core.config import get_settings

_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 10

# Hash usado quando o e-mail não existe, para que o tempo de resposta não revele contas válidas.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(admin_id: int) -> tuple[str, int]:
    settings = get_settings()
    now = now_utc()
    expires_in = settings.access_token_minutes * 60
    payload = {
        "sub": str(admin_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM), expires_in


class TokenExpired(Exception):
    pass


class TokenInvalid(Exception):
    pass


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid from exc
    if payload.get("type") != "access":
        raise TokenInvalid
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise TokenInvalid from exc


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def refresh_expiry() -> datetime:
    return now_utc() + timedelta(hours=get_settings().refresh_token_hours)
