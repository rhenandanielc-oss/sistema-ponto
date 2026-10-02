from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.biometrics.crypto import parse_key

INSECURE_SECRET_MARKERS = ("change-me", "changeme", "example", "secret")
# Chave só para desenvolvimento e testes (32 bytes zero). Proibida em produção.
DEV_BIOMETRIC_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://ponto:ponto@localhost:5432/ponto"

    jwt_secret: str = Field(default="dev-only-insecure-jwt-key-change-me-000000")
    access_token_minutes: int = 15
    refresh_token_hours: int = 8
    cookie_secure: bool = True

    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    app_timezone: str = "America/Sao_Paulo"
    cors_origins: list[str] = []
    rate_limit_enabled: bool = True
    log_format: Literal["json", "text"] = "text"
    log_level: str = "INFO"

    # Biometria (BIOMETRICS.md). A chave cifra os templates e NUNCA vai para o banco nem para o Git.
    biometric_key: str = DEV_BIOMETRIC_KEY
    biometric_key_id: str = "k1"
    face_engine: Literal["opencv", "fake"] = "opencv"
    face_models_dir: str = "models"
    face_match_threshold: float = Field(default=0.363, ge=0.0, le=1.0)  # referência do SFace
    face_match_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    face_min_size_px: int = Field(default=80, ge=20)
    kiosk_identification_seconds: int = Field(default=60, ge=10, le=300)

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.environment == "production":
            secret = self.jwt_secret
            if len(secret.encode()) < 32 or any(
                m in secret.lower() for m in INSECURE_SECRET_MARKERS
            ):
                raise ValueError("JWT_SECRET ausente, fraco ou com valor de exemplo em produção")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE deve ser true em produção")
            if self.biometric_key == DEV_BIOMETRIC_KEY:
                raise ValueError(
                    "BIOMETRIC_KEY ausente ou com o valor de desenvolvimento em produção"
                )
            if self.face_engine != "opencv":
                raise ValueError("FACE_ENGINE=fake é só para testes; proibido em produção")
        parse_key(self.biometric_key)  # falha cedo se a chave for inválida
        ZoneInfo(self.app_timezone)  # falha cedo se o fuso for inválido
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
