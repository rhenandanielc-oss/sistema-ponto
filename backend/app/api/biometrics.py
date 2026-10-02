from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import Actor, DbSession, get_current_admin
from app.biometrics.engine import FaceEngine, get_face_engine
from app.core.errors import AppError
from app.schemas.common import LocalDatetime
from app.services import biometric_service

router = APIRouter(
    prefix="/employees/{employee_id}",
    tags=["biometria"],
    dependencies=[Depends(get_current_admin)],
)

Engine = Annotated[FaceEngine, Depends(get_face_engine)]
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 1024 * 1024


async def read_image(image: UploadFile) -> bytes:
    """Lê a foto só para a memória (nunca para disco) e confere tipo e tamanho."""
    if image.content_type not in ALLOWED_TYPES:
        raise AppError(422, "INVALID_IMAGE", "Envie uma foto JPEG ou PNG.")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError(413, "PAYLOAD_TOO_LARGE", "Foto muito grande (máximo 1 MB).")
    return data


class ConsentIn(BaseModel):
    term_version: str = Field(default=biometric_service.CURRENT_TERM_VERSION, max_length=20)


class BiometricStatusOut(BaseModel):
    consent: bool
    consent_granted_at: LocalDatetime | None
    term_version: str | None
    templates: int = Field(
        description="Fotos de rosto cadastradas (só o vetor cifrado, nunca a imagem)"
    )
    max_templates: int = biometric_service.MAX_TEMPLATES
    ready: bool = Field(description="Pode bater ponto pelo rosto")


def _status(db: DbSession, employee_id: int, engine: FaceEngine) -> BiometricStatusOut:
    s = biometric_service.status(db, employee_id, engine.model_version)
    return BiometricStatusOut(
        consent=s.consent is not None,
        consent_granted_at=s.consent.granted_at if s.consent else None,
        term_version=s.consent.term_version if s.consent else None,
        templates=s.templates,
        ready=s.consent is not None and s.templates > 0,
    )


@router.get("/biometric-status", response_model=BiometricStatusOut)
def biometric_status(employee_id: int, db: DbSession, engine: Engine) -> BiometricStatusOut:
    return _status(db, employee_id, engine)


@router.post("/biometric-consent", response_model=BiometricStatusOut)
def grant_consent(
    employee_id: int, data: ConsentIn, db: DbSession, actor: Actor, engine: Engine
) -> BiometricStatusOut:
    """Registra que o funcionário consentiu com o uso da biometria facial (LGPD)."""
    biometric_service.grant_consent(db, employee_id, data.term_version, actor)
    return _status(db, employee_id, engine)


@router.delete("/biometric-consent", status_code=204)
def revoke_consent(employee_id: int, db: DbSession, actor: Actor) -> Response:
    """Revoga o consentimento e exclui as fotos cadastradas."""
    biometric_service.revoke_consent(db, employee_id, actor)
    return Response(status_code=204)


@router.post("/biometric-templates", response_model=BiometricStatusOut, status_code=201)
async def enroll(
    employee_id: int,
    db: DbSession,
    actor: Actor,
    engine: Engine,
    image: Annotated[UploadFile, File(description="Foto do rosto (JPEG/PNG, até 1 MB)")],
) -> BiometricStatusOut:
    """Cadastra uma foto do rosto. Só o vetor numérico cifrado é guardado."""
    data = await read_image(image)
    biometric_service.enroll(db, employee_id, data, engine, actor)
    return _status(db, employee_id, engine)


@router.delete("/biometric-templates", status_code=204)
def delete_templates(employee_id: int, db: DbSession, actor: Actor) -> Response:
    biometric_service.delete_templates(db, employee_id, actor)
    return Response(status_code=204)
