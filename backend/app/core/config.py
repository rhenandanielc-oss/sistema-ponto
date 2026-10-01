from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_MARKERS = ("change-me", "changeme", "example", "secret")


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
        ZoneInfo(self.app_timezone)  # falha cedo se o fuso for inválido
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
