"""Limpeza periódica (`python -m app.cli maintenance`), agendada em produção (DEPLOY.md)."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.models import KioskIdentification, RefreshToken
from app.services import audit, biometric_service

# Tokens vencidos ficam um tempo antes de sair: o refresh antigo ainda serve para detectar reuso.
EXPIRED_TOKEN_RETENTION = timedelta(days=7)


@dataclass(frozen=True)
class MaintenanceResult:
    biometric_templates: int
    kiosk_identifications: int
    refresh_tokens: int


def run(db: Session) -> MaintenanceResult:
    templates = biometric_service.purge_deleted(db)
    cutoff = now_utc() - EXPIRED_TOKEN_RETENTION
    identifications = db.execute(
        delete(KioskIdentification).where(KioskIdentification.expires_at < cutoff)
    ).rowcount  # type: ignore[attr-defined]
    tokens = db.execute(delete(RefreshToken).where(RefreshToken.expires_at < cutoff)).rowcount  # type: ignore[attr-defined]
    result = MaintenanceResult(int(templates), int(identifications or 0), int(tokens or 0))
    audit.record(
        db,
        actor=audit.SYSTEM,
        action="system.maintenance",
        after={
            "kiosk_identifications": result.kiosk_identifications,
            "refresh_tokens": result.refresh_tokens,
        },
    )
    db.commit()
    return result
