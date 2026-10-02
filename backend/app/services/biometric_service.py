"""Consentimento, cadastro do rosto e identificação no terminal (BIOMETRICS.md).

Regras de privacidade aplicadas aqui:
* nenhuma imagem é gravada (a imagem só existe na memória durante a chamada);
* só embeddings cifrados (AES-256-GCM) vão para o banco;
* cadastro exige consentimento vigente; revogar o consentimento ou desativar o funcionário
  exclui os templates;
* a auditoria registra os eventos, nunca a imagem nem o template.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.biometrics.crypto import SealedTemplate, TemplateCipher, parse_key
from app.biometrics.engine import FaceEngine, FaceError
from app.biometrics.matcher import best_match
from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError, conflict, not_found
from app.core.security import new_opaque_token, sha256_hex
from app.models import (
    BiometricConsent,
    BiometricTemplate,
    Device,
    Employee,
    KioskIdentification,
)
from app.services import audit, employee_service

MAX_TEMPLATES = 5
CURRENT_TERM_VERSION = "v1"
PURGE_AFTER_DAYS = 30


def _cipher() -> TemplateCipher:
    settings = get_settings()
    return TemplateCipher(parse_key(settings.biometric_key), settings.biometric_key_id)


def _face_error(error: FaceError) -> AppError:
    return AppError(422, error.code, error.message)


# --- Consentimento ------------------------------------------------------------------------------


def active_consent(db: Session, employee_id: int) -> BiometricConsent | None:
    return db.scalar(
        select(BiometricConsent).where(
            BiometricConsent.employee_id == employee_id, BiometricConsent.revoked_at.is_(None)
        )
    )


def grant_consent(
    db: Session, employee_id: int, term_version: str, actor: audit.Actor
) -> BiometricConsent:
    employee_service.get(db, employee_id)
    current = active_consent(db, employee_id)
    if current is not None:
        return current
    if actor.admin_id is None:
        raise AppError(403, "FORBIDDEN", "Somente administradores registram consentimento.")
    consent = BiometricConsent(
        employee_id=employee_id,
        term_version=term_version,
        granted_at=now_utc(),
        recorded_by_admin_id=actor.admin_id,
    )
    db.add(consent)
    audit.record(
        db,
        actor=actor,
        action="biometric.consent_granted",
        entity_type="employee",
        entity_id=employee_id,
        after={"term_version": term_version},
    )
    db.commit()
    return consent


def revoke_consent(db: Session, employee_id: int, actor: audit.Actor) -> None:
    """Revoga o consentimento e exclui os templates na mesma transação (BIOMETRICS.md §6)."""
    employee_service.get(db, employee_id)
    consent = active_consent(db, employee_id)
    if consent is None:
        return
    consent.revoked_at = now_utc()
    removed = _soft_delete_templates(db, employee_id)
    audit.record(
        db,
        actor=actor,
        action="biometric.consent_revoked",
        entity_type="employee",
        entity_id=employee_id,
        after={"templates_deleted": removed},
    )
    db.commit()


# --- Templates ----------------------------------------------------------------------------------


def _active_templates_query(employee_id: int):  # type: ignore[no-untyped-def]
    return select(BiometricTemplate).where(
        BiometricTemplate.employee_id == employee_id, BiometricTemplate.deleted_at.is_(None)
    )


def _soft_delete_templates(db: Session, employee_id: int) -> int:
    result = db.execute(
        update(BiometricTemplate)
        .where(BiometricTemplate.employee_id == employee_id, BiometricTemplate.deleted_at.is_(None))
        .values(deleted_at=now_utc())
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def enroll(
    db: Session, employee_id: int, image: bytes, engine: FaceEngine, actor: audit.Actor
) -> BiometricTemplate:
    """Cadastra um template a partir de uma foto. A foto não é guardada."""
    employee = employee_service.get(db, employee_id, for_update=True)
    if employee.status != "ACTIVE":
        raise conflict("EMPLOYEE_INACTIVE", "Funcionário inativo.")
    if active_consent(db, employee_id) is None:
        raise conflict(
            "CONSENT_REQUIRED",
            "Registre o consentimento do funcionário antes de cadastrar o rosto.",
        )
    count = db.scalar(
        select(func.count()).select_from(_active_templates_query(employee_id).subquery())
    )
    if (count or 0) >= MAX_TEMPLATES:
        raise conflict(
            "CONFLICT",
            f"O funcionário já tem {MAX_TEMPLATES} fotos cadastradas. Exclua para refazer.",
        )
    try:
        extraction = engine.extract(image)
    except FaceError as exc:
        raise _face_error(exc) from exc

    sealed = _cipher().seal(extraction.embedding, employee_id=employee_id)
    template = BiometricTemplate(
        employee_id=employee_id,
        model_version=engine.model_version,
        ciphertext=sealed.ciphertext,
        nonce=sealed.nonce,
        key_id=sealed.key_id,
        quality_score=extraction.quality,
    )
    db.add(template)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="biometric.enrolled",
        entity_type="employee",
        entity_id=employee_id,
        after={"template_id": template.id},
    )
    db.commit()
    return template


def delete_templates(db: Session, employee_id: int, actor: audit.Actor) -> int:
    employee_service.get(db, employee_id)
    removed = _soft_delete_templates(db, employee_id)
    audit.record(
        db,
        actor=actor,
        action="biometric.templates_deleted",
        entity_type="employee",
        entity_id=employee_id,
        after={"templates_deleted": removed},
    )
    db.commit()
    return removed


def delete_templates_in_transaction(db: Session, employee_id: int) -> int:
    """Usado ao desativar o funcionário: exclui os templates sem fazer commit."""
    return _soft_delete_templates(db, employee_id)


@dataclass(frozen=True)
class BiometricStatus:
    consent: BiometricConsent | None
    templates: int
    model_version: str | None


def status(db: Session, employee_id: int, engine_version: str) -> BiometricStatus:
    employee_service.get(db, employee_id)
    count = db.scalar(
        select(func.count()).select_from(
            _active_templates_query(employee_id)
            .where(BiometricTemplate.model_version == engine_version)
            .subquery()
        )
    )
    return BiometricStatus(active_consent(db, employee_id), int(count or 0), engine_version)


def purge_deleted(db: Session, older_than_days: int = PURGE_AFTER_DAYS) -> int:
    """Expurgo físico dos templates excluídos há mais de N dias (BIOMETRICS.md §6)."""
    cutoff = now_utc() - timedelta(days=older_than_days)
    result = db.execute(
        delete(BiometricTemplate).where(
            BiometricTemplate.deleted_at.is_not(None), BiometricTemplate.deleted_at < cutoff
        )
    )
    removed = int(result.rowcount or 0)  # type: ignore[attr-defined]
    audit.record(db, actor=audit.SYSTEM, action="biometric.purged", after={"templates": removed})
    db.commit()
    return removed


# --- Identificação no terminal ------------------------------------------------------------------


@dataclass(frozen=True)
class Identification:
    token: str
    employee: Employee
    expires_at: datetime
    score: float


def identify(db: Session, image: bytes, engine: FaceEngine, device: Device) -> Identification:
    """1:N entre os funcionários ativos com consentimento. Emite um token de identificação curto."""
    settings = get_settings()
    device_actor = audit.Actor("DEVICE", device_id=device.id)

    def fail(error: AppError, **details: object) -> AppError:
        audit.record(
            db,
            actor=device_actor,
            action="kiosk.identify_failed",
            after={"code": error.code, **details},
        )
        db.commit()
        return error

    try:
        probe = engine.extract(image).embedding
    except FaceError as exc:
        raise fail(_face_error(exc)) from exc

    rows = (
        db.execute(
            select(BiometricTemplate)
            .join(Employee, Employee.id == BiometricTemplate.employee_id)
            .join(
                BiometricConsent,
                (BiometricConsent.employee_id == Employee.id)
                & BiometricConsent.revoked_at.is_(None),
            )
            .where(
                BiometricTemplate.deleted_at.is_(None),
                BiometricTemplate.model_version == engine.model_version,
                Employee.status == "ACTIVE",
            )
        )
        .scalars()
        .all()
    )
    cipher = _cipher()
    candidates = [
        (
            t.employee_id,
            cipher.open(SealedTemplate(t.ciphertext, t.nonce, t.key_id), employee_id=t.employee_id),
        )
        for t in rows
    ]
    result = best_match(
        probe,
        candidates,
        threshold=settings.face_match_threshold,
        margin=settings.face_match_margin,
    )
    if result.employee_id is None:
        raise fail(
            AppError(
                404,
                "FACE_NOT_RECOGNIZED",
                "Rosto não reconhecido. Tente novamente ou procure o administrador.",
            ),
            score=round(result.score, 3),
        )

    employee = employee_service.get(db, result.employee_id)
    token = new_opaque_token()
    expires_at = now_utc() + timedelta(seconds=settings.kiosk_identification_seconds)
    db.add(
        KioskIdentification(
            token_hash=sha256_hex(token),
            employee_id=employee.id,
            device_id=device.id,
            score=result.score,
            expires_at=expires_at,
        )
    )
    audit.record(
        db,
        actor=audit.Actor("DEVICE", device_id=device.id, employee_id=employee.id),
        action="kiosk.identified",
        entity_type="employee",
        entity_id=employee.id,
        after={"score": round(result.score, 3)},
    )
    db.commit()
    return Identification(token=token, employee=employee, expires_at=expires_at, score=result.score)


def resolve_token(db: Session, token: str, device: Device, *, consume: bool) -> KioskIdentification:
    """Valida o token de identificação. `consume=True` (batida) impede reutilização."""
    identification = db.scalar(
        select(KioskIdentification)
        .where(KioskIdentification.token_hash == sha256_hex(token))
        .with_for_update()
    )
    invalid = AppError(
        401, "IDENTIFICATION_REQUIRED", "Identificação expirada. Olhe para a câmera novamente."
    )
    if (
        identification is None
        or identification.device_id != device.id
        or identification.used_at is not None
        or identification.expires_at <= now_utc()
    ):
        db.rollback()
        raise invalid
    if consume:
        identification.used_at = now_utc()
        db.flush()
    return identification


def get_employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise not_found("Funcionário não encontrado.", code="EMPLOYEE_NOT_FOUND")
    return employee
