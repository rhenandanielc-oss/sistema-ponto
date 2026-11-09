from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.errors import AppError, not_found
from app.core.security import new_opaque_token, sha256_hex
from app.models import Device
from app.services import audit


def _snapshot(d: Device) -> dict[str, object]:
    return {"name": d.name, "is_active": d.is_active, "require_location": d.require_location}


ACTIVATION_LINK_HOURS = 24


def list_devices(db: Session) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.name, Device.id)).all())


def get(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise not_found("Dispositivo não encontrado.")
    return device


def create(
    db: Session, name: str, actor: audit.Actor, require_location: bool = False
) -> tuple[Device, str]:
    """Cadastra o terminal. O token devolvido é exibido uma única vez."""
    token = new_opaque_token()
    device = Device(name=name, token_hash=sha256_hex(token), require_location=require_location)
    db.add(device)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="device.create",
        entity_type="device",
        entity_id=device.id,
        after=_snapshot(device),
    )
    db.commit()
    return device, token


def rotate_token(db: Session, device_id: int, actor: audit.Actor) -> tuple[Device, str]:
    device = get(db, device_id)
    token = new_opaque_token()
    device.token_hash = sha256_hex(token)
    audit.record(
        db, actor=actor, action="device.rotate_token", entity_type="device", entity_id=device.id
    )
    db.commit()
    return device, token


def set_active(db: Session, device_id: int, active: bool, actor: audit.Actor) -> Device:
    device = get(db, device_id)
    if device.is_active != active:
        before = _snapshot(device)
        device.is_active = active
        audit.record(
            db,
            actor=actor,
            action="device.activate" if active else "device.deactivate",
            entity_type="device",
            entity_id=device.id,
            before=before,
            after=_snapshot(device),
        )
        db.commit()
    return device


def set_require_location(db: Session, device_id: int, required: bool, actor: audit.Actor) -> Device:
    device = get(db, device_id)
    if device.require_location != required:
        before = _snapshot(device)
        device.require_location = required
        audit.record(
            db,
            actor=actor,
            action="device.set_require_location",
            entity_type="device",
            entity_id=device.id,
            before=before,
            after=_snapshot(device),
        )
        db.commit()
    return device


def create_activation_link(db: Session, device_id: int, actor: audit.Actor) -> tuple[str, object]:
    """Gera um código de uso único (vale 24 h). Gerar outro invalida o anterior."""
    device = get(db, device_id)
    code = new_opaque_token()
    device.activation_hash = sha256_hex(code)
    device.activation_expires_at = now_utc() + timedelta(hours=ACTIVATION_LINK_HOURS)
    audit.record(
        db, actor=actor, action="device.activation_link", entity_type="device", entity_id=device.id
    )
    db.commit()
    return code, device.activation_expires_at


def activate_with_code(db: Session, code: str) -> tuple[Device, str]:
    """Troca o código de uso único por um token novo do terminal. O código deixa de valer."""
    device = db.scalar(select(Device).where(Device.activation_hash == sha256_hex(code)))
    expires = device.activation_expires_at if device is not None else None
    if device is None or not device.is_active or expires is None or expires < now_utc():
        raise AppError(
            403,
            "ACTIVATION_LINK_INVALID",
            "Link de ativação inválido ou vencido. Peça um novo ao administrador.",
        )
    token = new_opaque_token()
    device.token_hash = sha256_hex(token)  # o token anterior deste terminal deixa de valer
    device.activation_hash = None
    device.activation_expires_at = None
    device.last_seen_at = now_utc()
    audit.record(
        db,
        actor=audit.Actor("DEVICE", device_id=device.id),
        action="device.activated_by_link",
        entity_type="device",
        entity_id=device.id,
    )
    db.commit()
    return device, token


def authenticate(db: Session, token: str) -> Device | None:
    device = db.scalar(select(Device).where(Device.token_hash == sha256_hex(token)))
    if device is None or not device.is_active:
        return None
    device.last_seen_at = now_utc()
    db.commit()
    return device
